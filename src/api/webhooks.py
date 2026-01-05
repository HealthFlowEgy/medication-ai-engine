"""
Webhook Configuration and Management Module
Handles webhook registration, delivery, and retry logic for blocked prescription alerts
"""
import os
import hmac
import hashlib
import json
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebhookEventType(str, Enum):
    """Types of webhook events"""
    PRESCRIPTION_BLOCKED = "prescription.blocked"
    PRESCRIPTION_WARNING = "prescription.warning"
    MAJOR_INTERACTION = "interaction.major"
    CONTRAINDICATION = "contraindication.detected"
    DOSING_ALERT = "dosing.alert"
    SYSTEM_HEALTH = "system.health"


class WebhookStatus(str, Enum):
    """Webhook delivery status"""
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"


@dataclass
class WebhookConfig:
    """Webhook endpoint configuration"""
    id: str
    name: str
    url: str
    secret: str
    events: List[str]
    active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    headers: Dict[str, str] = field(default_factory=dict)
    retry_count: int = 3
    retry_delay_seconds: int = 60


@dataclass
class WebhookDelivery:
    """Record of a webhook delivery attempt"""
    id: str
    webhook_id: str
    event_type: str
    payload: Dict[str, Any]
    status: str
    attempts: int = 0
    last_attempt: Optional[str] = None
    response_code: Optional[int] = None
    response_body: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class WebhookManager:
    """
    Manages webhook configurations and delivery for the Medication Validation Engine.
    Supports HMAC signature verification and automatic retry logic.
    """
    
    def __init__(self):
        self.webhooks: Dict[str, WebhookConfig] = {}
        self.deliveries: List[WebhookDelivery] = []
        self.http_client = httpx.AsyncClient(timeout=30.0)
        
        # Load default HealthFlow webhook from environment
        healthflow_webhook_url = os.getenv("HEALTHFLOW_WEBHOOK_URL")
        healthflow_webhook_secret = os.getenv("HEALTHFLOW_WEBHOOK_SECRET", "healthflow-webhook-secret-2026")
        
        if healthflow_webhook_url:
            self.register_webhook(WebhookConfig(
                id="healthflow-main",
                name="HealthFlow Unified System",
                url=healthflow_webhook_url,
                secret=healthflow_webhook_secret,
                events=[
                    WebhookEventType.PRESCRIPTION_BLOCKED.value,
                    WebhookEventType.MAJOR_INTERACTION.value,
                    WebhookEventType.CONTRAINDICATION.value
                ],
                active=True
            ))
            logger.info(f"Registered HealthFlow webhook: {healthflow_webhook_url}")
    
    def register_webhook(self, config: WebhookConfig) -> WebhookConfig:
        """Register a new webhook endpoint"""
        self.webhooks[config.id] = config
        logger.info(f"Webhook registered: {config.name} ({config.id})")
        return config
    
    def update_webhook(self, webhook_id: str, updates: Dict[str, Any]) -> Optional[WebhookConfig]:
        """Update an existing webhook configuration"""
        if webhook_id not in self.webhooks:
            return None
        
        webhook = self.webhooks[webhook_id]
        for key, value in updates.items():
            if hasattr(webhook, key):
                setattr(webhook, key, value)
        
        logger.info(f"Webhook updated: {webhook_id}")
        return webhook
    
    def delete_webhook(self, webhook_id: str) -> bool:
        """Delete a webhook configuration"""
        if webhook_id in self.webhooks:
            del self.webhooks[webhook_id]
            logger.info(f"Webhook deleted: {webhook_id}")
            return True
        return False
    
    def list_webhooks(self) -> List[Dict[str, Any]]:
        """List all registered webhooks (with secrets masked)"""
        return [
            {
                "id": w.id,
                "name": w.name,
                "url": w.url,
                "secret": w.secret[:8] + "..." if w.secret else None,
                "events": w.events,
                "active": w.active,
                "created_at": w.created_at
            }
            for w in self.webhooks.values()
        ]
    
    def generate_signature(self, payload: str, secret: str) -> str:
        """Generate HMAC-SHA256 signature for webhook payload"""
        return hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
    
    def verify_signature(self, payload: str, signature: str, secret: str) -> bool:
        """Verify webhook signature"""
        expected = self.generate_signature(payload, secret)
        return hmac.compare_digest(expected, signature)
    
    async def send_webhook(
        self,
        webhook: WebhookConfig,
        event_type: str,
        payload: Dict[str, Any]
    ) -> WebhookDelivery:
        """Send a webhook notification"""
        
        delivery_id = f"del-{datetime.now().strftime('%Y%m%d%H%M%S')}-{webhook.id}"
        
        delivery = WebhookDelivery(
            id=delivery_id,
            webhook_id=webhook.id,
            event_type=event_type,
            payload=payload,
            status=WebhookStatus.PENDING.value
        )
        
        # Prepare payload with metadata
        full_payload = {
            "event": event_type,
            "timestamp": datetime.now().isoformat(),
            "delivery_id": delivery_id,
            "data": payload
        }
        
        payload_str = json.dumps(full_payload, sort_keys=True)
        signature = self.generate_signature(payload_str, webhook.secret)
        
        headers = {
            "Content-Type": "application/json",
            "X-Webhook-Signature": signature,
            "X-Webhook-Event": event_type,
            "X-Webhook-Delivery": delivery_id,
            **webhook.headers
        }
        
        # Attempt delivery with retries
        for attempt in range(webhook.retry_count):
            delivery.attempts = attempt + 1
            delivery.last_attempt = datetime.now().isoformat()
            
            try:
                response = await self.http_client.post(
                    webhook.url,
                    content=payload_str,
                    headers=headers
                )
                
                delivery.response_code = response.status_code
                delivery.response_body = response.text[:500] if response.text else None
                
                if response.status_code in [200, 201, 202, 204]:
                    delivery.status = WebhookStatus.DELIVERED.value
                    logger.info(f"Webhook delivered: {delivery_id} to {webhook.url}")
                    break
                else:
                    delivery.status = WebhookStatus.RETRYING.value
                    logger.warning(f"Webhook failed (attempt {attempt + 1}): {response.status_code}")
                    
            except Exception as e:
                delivery.status = WebhookStatus.RETRYING.value
                delivery.response_body = str(e)[:500]
                logger.error(f"Webhook error (attempt {attempt + 1}): {e}")
            
            # Wait before retry
            if attempt < webhook.retry_count - 1:
                await asyncio.sleep(webhook.retry_delay_seconds)
        
        if delivery.status == WebhookStatus.RETRYING.value:
            delivery.status = WebhookStatus.FAILED.value
            logger.error(f"Webhook delivery failed after {webhook.retry_count} attempts: {delivery_id}")
        
        self.deliveries.append(delivery)
        return delivery
    
    async def trigger_event(
        self,
        event_type: str,
        payload: Dict[str, Any]
    ) -> List[WebhookDelivery]:
        """Trigger an event and send to all subscribed webhooks"""
        
        deliveries = []
        
        for webhook in self.webhooks.values():
            if not webhook.active:
                continue
            
            if event_type in webhook.events or "*" in webhook.events:
                delivery = await self.send_webhook(webhook, event_type, payload)
                deliveries.append(delivery)
        
        return deliveries
    
    async def send_blocked_prescription_alert(
        self,
        prescription_id: str,
        patient_id: str,
        reason: str,
        interactions: List[Dict[str, Any]] = None,
        contraindications: List[str] = None,
        pharmacy_id: str = None,
        prescriber_id: str = None
    ) -> List[WebhookDelivery]:
        """
        Send alert for a blocked prescription.
        This is the main entry point for blocked prescription notifications.
        """
        
        payload = {
            "prescription_id": prescription_id,
            "patient_id": patient_id,
            "status": "BLOCKED",
            "reason": reason,
            "pharmacy_id": pharmacy_id,
            "prescriber_id": prescriber_id,
            "blocked_at": datetime.now().isoformat(),
            "details": {
                "interactions": interactions or [],
                "contraindications": contraindications or []
            },
            "action_required": True,
            "severity": "HIGH"
        }
        
        return await self.trigger_event(
            WebhookEventType.PRESCRIPTION_BLOCKED.value,
            payload
        )
    
    async def send_major_interaction_alert(
        self,
        prescription_id: str,
        drug1: str,
        drug2: str,
        severity: str,
        mechanism: str,
        management: str
    ) -> List[WebhookDelivery]:
        """Send alert for major drug interaction detected"""
        
        payload = {
            "prescription_id": prescription_id,
            "interaction": {
                "drug1": drug1,
                "drug2": drug2,
                "severity": severity,
                "mechanism": mechanism,
                "management": management
            },
            "detected_at": datetime.now().isoformat()
        }
        
        return await self.trigger_event(
            WebhookEventType.MAJOR_INTERACTION.value,
            payload
        )
    
    def get_delivery_history(
        self,
        webhook_id: str = None,
        event_type: str = None,
        status: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get webhook delivery history with optional filters"""
        
        filtered = self.deliveries
        
        if webhook_id:
            filtered = [d for d in filtered if d.webhook_id == webhook_id]
        if event_type:
            filtered = [d for d in filtered if d.event_type == event_type]
        if status:
            filtered = [d for d in filtered if d.status == status]
        
        # Return most recent first
        filtered = sorted(filtered, key=lambda d: d.created_at, reverse=True)
        
        return [asdict(d) for d in filtered[:limit]]


# Singleton instance
_webhook_manager: Optional[WebhookManager] = None


def get_webhook_manager() -> WebhookManager:
    """Get or create webhook manager singleton"""
    global _webhook_manager
    if _webhook_manager is None:
        _webhook_manager = WebhookManager()
    return _webhook_manager
