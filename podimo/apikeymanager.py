import os
import time
from datetime import datetime, timedelta


class APIKeyManager:
    _instance = None

    @staticmethod
    def getInstance():
        if APIKeyManager._instance is None:
            APIKeyManager()
        return APIKeyManager._instance

    def __init__(self):
        if APIKeyManager._instance is not None:
            raise Exception("This class is a singleton!")
        else:
            # Load API keys from config (environment variable)
            self.api_keys = os.getenv('SCRAPER_API_KEYS', '').split(',')

            if not self.api_keys or self.api_keys == ['']:
                print("Warning: No API keys found in SCRAPER_API_KEYS")

            self.api_key_status = {key: {'active': True, 'next_available_time': None} for key in self.api_keys if key}
            APIKeyManager._instance = self

    def set_key_inactive(self, key):
        if key in self.api_key_status:
            self.api_key_status[key]['active'] = False
            self.api_key_status[key]['next_available_time'] = datetime.now() + timedelta(hours=24)
        else:
            print(f"Warning: Attempted to set inactive status for unknown API key '{key}'")

    def get_active_key(self):
        for key, status in self.api_key_status.items():
            if status['active']:
                return key
            elif datetime.now() >= status['next_available_time']:
                status['active'] = True
                return key
        return None  # Return None if no active API keys are available



