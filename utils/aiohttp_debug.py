import aiohttp
import logging
import traceback

# глобальный реестр активных сессий
_active_sessions = set()

# сохраняем старые методы
_old_init = aiohttp.ClientSession.__init__
_old_close = aiohttp.ClientSession.close

def _new_init(self, *args, **kwargs):
    _old_init(self, *args, **kwargs)
    _active_sessions.add(self)
    logging.error(f"[TRACK] Created ClientSession {hex(id(self))}\n" +
                  "".join(traceback.format_stack(limit=5)))

async def _new_close(self, *args, **kwargs):
    if self in _active_sessions:
        _active_sessions.remove(self)
        logging.error(f"[TRACK] Closed ClientSession {hex(id(self))}")
    return await _old_close(self, *args, **kwargs)

aiohttp.ClientSession.__init__ = _new_init
aiohttp.ClientSession.close = _new_close

def print_active_sessions(where: str = ""):
    """Печатает список всех открытых ClientSession"""
    if not _active_sessions:
        logging.info(f"[SESSIONS] No active sessions {where}")
    else:
        for s in _active_sessions:
            logging.warning(f"[SESSIONS] Active session {hex(id(s))} {where}")
