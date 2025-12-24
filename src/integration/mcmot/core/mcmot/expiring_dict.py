import time

class ExpiringDict:
    def __init__(self, expiration_seconds=60):
        self.store = {}
        self.timestamps = {}
        self.expiration_seconds = expiration_seconds

    def set(self, key, value):
        self.store[key] = value
        self.timestamps[key] = time.time()

    def get(self, key, default=None):
        if key in self.store and not self._is_expired(key):
            return self.store[key]
        else:
            self._remove(key)
            return default

    def _is_expired(self, key):
        return (time.time() - self.timestamps.get(key, 0)) > self.expiration_seconds

    def _remove(self, key):
        self.store.pop(key, None)
        self.timestamps.pop(key, None)

    def cleanup(self):
        keys_to_remove = [key for key in self.store if self._is_expired(key)]
        for key in keys_to_remove:
            self._remove(key)

    def __contains__(self, key):
        if key in self.store and not self._is_expired(key):
            return True
        self._remove(key)
        return False

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.set(key, value)

    def __delitem__(self, key):
        self._remove(key)

    def items(self):
        self.cleanup()
        return self.store.items()

    def get_store(self):
        self.cleanup()
        return self.store
