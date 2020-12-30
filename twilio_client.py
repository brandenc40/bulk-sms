import os
from typing import Optional

from flask import _app_ctx_stack, current_app, Flask
from twilio.rest import Client


class TwilioClient(object):
    def __init__(self, app: Optional[Flask] = None):
        self.app = app
        if app is not None:
            app.config.setdefault('TWILIO_ACCOUNT_SID', os.getenv('TWILIO_ACCOUNT_SID'))
            app.config.setdefault('TWILIO_AUTH_TOKEN', os.getenv('TWILIO_AUTH_TOKEN'))
            app.config.setdefault('TWILIO_PHONE_NUMBER', os.getenv('TWILIO_PHONE_NUMBER'))

    @property
    def client(self):
        ctx = _app_ctx_stack.top
        if ctx is not None:
            if not hasattr(ctx, 'twilio_client'):
                ctx.twilio_client = Client(
                    current_app.config['TWILIO_ACCOUNT_SID'],
                    current_app.config['TWILIO_AUTH_TOKEN']
                )
            return ctx.twilio_client

    def send_message(self, to: str, message: str, media_url: Optional[str] = None):
        if media_url:
            self.client.messages.create(
                to=to,
                from_=current_app.config['TWILIO_PHONE_NUMBER'],
                body=message,
                media_url=media_url
            )
        else:
            self.client.messages.create(
                to=to,
                from_=current_app.config['TWILIO_PHONE_NUMBER'],
                body=message
            )
