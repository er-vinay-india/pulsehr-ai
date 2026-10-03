"""Serialize upload/deletion and publication of generated data in this API process."""
import threading

data_lifecycle_lock = threading.RLock()
