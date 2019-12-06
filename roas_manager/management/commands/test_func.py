from django.core.management.base import BaseCommand
from roas_manager.google_sheets import *
from roas_manager.tools import *
from roas_manager.maintanence import *
from roas_manager.google_cloud_platform import *
from roas_manager.google_ads import *
from django.core.exceptions import ObjectDoesNotExist
from datetime import datetime
from django.core.mail import send_mail
import smtplib
import ssl
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Testing'

    def handle(self, *args, **kwargs):
        logger.info("Logger message")
