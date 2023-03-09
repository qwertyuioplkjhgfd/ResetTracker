from enum import Enum
import uuid
import aiohttp
from typing import Optional, Callable
import webbrowser
from aiohttp import ClientSession, web
import asyncio
from threading import Thread
from time import sleep
from concurrent.futures._base import CancelledError
from logging import getLogger, Logger
import traceback
from typing import List, Union

import urllib.parse

NIGHTBOT_AUTH_BASE_URL = 'https://api.nightbot.tv/'
NIGHTBOT_API_BASE_URL = 'https://api.nightbot.tv/'

def build_url(url: str, params: dict, remove_none: bool = False, split_lists: bool = False, enum_value: bool = True) -> str:
    """Build a valid url string

    :param url: base URL
    :param params: dictionary of URL parameter
    :param remove_none: if set all params that have a None value get removed |default| :code:`False`
    :param split_lists: if set all params that are a list will be split over multiple url parameter with the same name |default| :code:`False`
    :param enum_value: if true, automatically get value string from Enum values |default| :code:`True`
    :return: URL
    """

    def get_val(val):
        if not enum_value:
            return str(val)
        if isinstance(val, Enum):
            return str(val.value)
        return str(val)

    def add_param(res, k, v):
        if len(res) > 0:
            res += "&"
        res += str(k)
        if v is not None:
            res += "=" + urllib.parse.quote(get_val(v))
        return res

    result = ""
    for key, value in params.items():
        if value is None and remove_none:
            continue
        if split_lists and isinstance(value, list):
            for va in value:
                result = add_param(result, key, va)
        else:
            result = add_param(result, key, value)
    return url + (("?" + result) if len(result) > 0 else "")

def build_scope(scopes):
    return ' '.join([s.value for s in scopes])


class Nightbot:
    def __init__(self, client_id):
        self.client_id = client_id
        self.user_token = None
        self.scopes = None
        self._commands = None
        self._session = ClientSession(base_url=NIGHTBOT_API_BASE_URL)
        
    async def set_user_authentication(self, user_token, scopes):
        self.user_token = user_token
        self.scopes = scopes
        self._session.headers.update({'Authorization': 'Bearer ' + self.user_token})
    
    async def edit_command(self, name, content):
        await self._load_commands()
        
        for command in self._commands["commands"]:
            if command["name"] == name:
                async with self._session.put('/1/commands/'+command["_id"], data={"message":content}) as response:
                    if response.status != 200:
                        print('Error editing nightbot command: ', await response.json())
                    return
        
        print('warning: could not find command ' + name + ', please add it to nightbot')
        # invalidate current cache
        self._commands = None
    
    async def _load_commands(self):
        """
        loads nightbot commands into self.commands if not already
        """
        if self._commands is None:
            async with self._session.get('/1/commands') as response:
                if response.status != 200:
                    print('Error fetching nightbot commands: ', await response.json())
                self._commands = await response.json()
    
    async def stop(self):
        await self._session.close()


class AuthScope(Enum):
    CHANNEL = 'channel'
    CHANNEL_SEND = 'channel_send'
    COMMANDS = 'commands'
    COMMANDS_DEFAULT = 'commands_default'
    REGULARS = 'regulars'
    SONG_REQUESTS = 'song_requests'
    SONG_REQUESTS_QUEUE = 'song_requests_queue'
    SONG_REQUESTS_PLAYLIST = 'song_requests_playlist'
    SPAM_PROTECTION = 'spam_protection'
    SUBSCRIBERS = 'subscribers'
    TIMERS = 'timers'


class NightbotImplAuthenticator:
    """Simple to use client for the Nightbot implicit authentication flow.
       """

    def __init__(self,
                 nightbot: 'Nightbot',
                 scopes: List[AuthScope],
                 url: str = 'http://localhost:17563'):
        """
        :param nightbot: A nightbot instance
        :param scopes: List of the desired Auth scopes
        :param url: The reachable URL that will be opened in the browser. |default| :code:`http://localhost:17563`
        """
        self.__nightbot: 'Nightbot' = nightbot
        self.__client_id: str = nightbot.client_id
        self.scopes: List[AuthScope] = scopes
        self.logger: Logger = getLogger('nightbotauth.oauth')
        """The logger used for OAuth related log messages"""
        self.url = url
        self.redirect_document: str = """<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Nightbot OAuth</title>
        </head>
        <body>
            <h1>Redirecting you...</h1>
            <script>
            window.location = "http://localhost:17563/" + "?" + document.location.hash.substring(1)
            </script>
        </body>
        </html>"""
        self.document: str = """<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <title>Nightbot OAuth</title>
        </head>
        <body>
            <h1>Thanks for Authenticating with Nightbot!</h1>
            You may now close this page.
            <script>
            //dude i spent like an hour trying to figure out why this doesn't work but twitch's works
            //still have zero idea
            setTimeout(function() {
                window.close();
                }, 5000);
            </script>
        </body>
        </html>"""
        """The document that will be rendered at the end of the flow"""
        self.port: int = 17563
        """The port that will be used. |default| :code:`17654`"""
        self.host: str = '0.0.0.0'
        """the host the webserver will bind to. |default| :code:`0.0.0.0`"""
        self.state: str = str(uuid.uuid4())
        self.__callback_func = None
        self.__server_running: bool = False
        self.__loop: Union[asyncio.AbstractEventLoop, None] = None
        self.__runner: Union[web.AppRunner, None] = None
        self.__thread: Union[Thread, None] = None
        self.__user_token: Union[str, None] = None
        self.__can_close: bool = False
        self.__is_closed = False

    def __build_auth_url(self):
        params = {
            'client_id': self.__nightbot.client_id,
            'redirect_uri': self.url,
            'response_type': 'token',
            'scope': build_scope(self.scopes),
            'state': self.state
        }
        return build_url(NIGHTBOT_AUTH_BASE_URL + 'oauth2/authorize', params)

    def __build_runner(self):
        app = web.Application()
        app.add_routes([web.route('*', '/', self.__handle_callback)])
        return web.AppRunner(app)

    async def __run_check(self):
        while not self.__can_close:
            await asyncio.sleep(0.1)
        await self.__runner.shutdown()
        await self.__runner.cleanup()
        self.logger.info('shutting down oauth Webserver')
        self.__is_closed = True

    def __run(self, runner: web.AppRunner):
        self.__runner = runner
        self.__loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.__loop)
        self.__loop.run_until_complete(runner.setup())
        site = web.TCPSite(runner, self.host, self.port)
        self.__loop.run_until_complete(site.start())
        self.__server_running = True
        self.logger.info('running oauth Webserver')
        try:
            self.__loop.run_until_complete(self.__run_check())
        except (CancelledError, asyncio.CancelledError):
            pass

    def __start(self):
        self.__thread = Thread(target=self.__run, args=(self.__build_runner(),))
        self.__thread.start()

    def stop(self):
        """Manually stop the flow

        :rtype: None
        """
        self.__can_close = True

    async def __handle_callback(self, request: web.Request):
        error = request.rel_url.query.get('error')
        if error is not None:
            print(f'Error authenticating with nightbot: {error}')
            return web.Response(status=401)
        
        val = request.rel_url.query.get('state')
        if val is None:
            return web.Response(text=self.redirect_document, content_type='text/html')

        self.logger.debug(f'got callback with state {val}')
        # invalid state!
        if val != self.state:
            return web.Response(status=401)
        self.__user_token = request.rel_url.query.get('access_token')
        if self.__user_token is None:
            # must provide code
            return web.Response(status=400)
        if self.__callback_func is not None:
            self.__callback_func(self.__user_token)
        return web.Response(text=self.document, content_type='text/html')

    def return_auth_url(self):
        """Returns the URL that will authenticate the app, used for headless server environments."""
        return self.__build_auth_url()

    async def authenticate(self,
                           callback_func: Optional[Callable[[str, str], None]] = None,
                           browser_name: Optional[str] = None,
                           browser_new: int = 2):
        """Start the user authentication flow\n
        If callback_func is not set, authenticate will wait till the authentication process finished and then return
        the access_token

        :param callback_func: Function to call once the authentication finished.
        :param browser_name: The browser that should be used, None means that the system default is used.
                            See `the webbrowser documentation <https://docs.python.org/3/library/webbrowser.html#webbrowser.register>`__ for more info
                            |default|:code:`None`
        :param browser_new: controls in which way the link will be opened in the browser.
                            See `the webbrowser documentation <https://docs.python.org/3/library/webbrowser.html#webbrowser.open>`__ for more info
                            |default|:code:`2`
        :rtype: None or (str, str)
        """
        self.__callback_func = callback_func
        self.__can_close = False
        self.__user_token = None
        self.__is_closed = False

        self.__start()
        # wait for the server to start up
        while not self.__server_running:
            sleep(0.01)
        # open in browser
        browser = webbrowser.get(browser_name)
        toopenurl = self.__build_auth_url()
        print("opening url " + toopenurl)
        browser.open(toopenurl, new=browser_new)
        
        while self.__user_token is None:
            sleep(0.01)
        self.stop()
        while not self.__is_closed:
            await asyncio.sleep(0.1)
        return self.__user_token 


async def nightbot_example():
    nbot = Nightbot('3df83e4d6c9bfafc5c25f3f6669fe59f')

    scopes = [AuthScope.CHANNEL_SEND, AuthScope.COMMANDS]
    
    auth = NightbotImplAuthenticator(nbot, scopes)
    token = await auth.authenticate()
    await nbot.set_user_authentication(token, scopes)
    
    await nbot.edit_command("!today", "this is a nightbot test 1")
    
    await nbot.stop()

if __name__ == "__main__":
    # run this example
    asyncio.run(nightbot_example())

