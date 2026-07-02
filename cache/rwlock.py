"""
RWLock
======
Readers-Writer Lock — standard threading.Lock() se smarter.

Problem with normal Lock:
  GET request aaye -> lock lo -> value padho -> lock chodo
  Agar 100 GET ek saath aayein, sab queue mein wait karenge.
  Yeh bekar hai — sirf padhna toh safe hai parallel mein.

RWLock ka solution:
  READ  -> multiple threads ek saath padh sakte hain (no blocking)
  WRITE -> sirf ek thread likhega, baaki sab wait karenge

Cache mein GET (read) bahut zyada hoti hain vs PUT (write),
isliye RWLock se performance kaafi better hoti hai.

Internals:
  _readers    -> kitne threads abhi padh rahe hain
  _read_ready -> Condition object — write thread yahan wait karta hai
                 jab tak readers 0 na ho jaayein
"""

import threading


class RWLock:
    def __init__(self) -> None:
        self._read_ready = threading.Condition(threading.Lock())
        self._readers = 0

    def read_acquire(self) -> None:
        """Read lock lo — reader count badhao."""
        with self._read_ready:
            self._readers += 1

    def read_release(self) -> None:
        """Read lock chodo — reader count ghataao, writer ko notify karo."""
        with self._read_ready:
            self._readers -= 1
            if self._readers == 0:
                self._read_ready.notify_all()  # writer ab aage badh sakta hai

    def write_acquire(self) -> None:
        """Write lock lo — sare readers khatam hone ka wait karo."""
        self._read_ready.acquire()
        while self._readers > 0:
            self._read_ready.wait()  # readers hain — wait karo

    def write_release(self) -> None:
        """Write lock chodo."""
        self._read_ready.release()

    # ── Context managers — `with lock.read():` syntax ke liye ─────────────

    class _ReadCtx:
        def __init__(self, lock: "RWLock") -> None:
            self._lock = lock

        def __enter__(self):
            self._lock.read_acquire()
            return self

        def __exit__(self, *_):
            self._lock.read_release()

    class _WriteCtx:
        def __init__(self, lock: "RWLock") -> None:
            self._lock = lock

        def __enter__(self):
            self._lock.write_acquire()
            return self

        def __exit__(self, *_):
            self._lock.write_release()

    def read(self) -> "_ReadCtx":
        return self._ReadCtx(self)

    def write(self) -> "_WriteCtx":
        return self._WriteCtx(self)