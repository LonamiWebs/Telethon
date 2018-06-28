import threading


def create_task(method, *args, **kwargs):
    thread = threading.Thread(target=method, daemon=True,
                              args=args, kwargs=kwargs)
    thread.start()
    return thread
