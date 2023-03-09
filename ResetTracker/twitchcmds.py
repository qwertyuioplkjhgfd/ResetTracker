from twitchAPI import Twitch
from twitchAPI.helper import first
from twitchAPI.types import AuthScope, TwitchAPIException
from twitchAPI.chat import Chat
from commandupdater import CommandUpdater
from twitchauth import ImplicitAuthenticator
import asyncio
from datetime import datetime, timedelta

def tostring(list):
    if len(list) == 0:
        return ""
    return f"[{', '.join(list)}]"

class TwitchCommandUpdater(CommandUpdater):
    def __init__(self, settings: dict):
        super().__init__(settings)
        self.twitch = None
        self.chat = None
        self.room = None

    async def setup(self):
        # assert self.settings['twitch']['method'] == 'chat'
        twitchsettings = self.settings['twitch']
        
        if 'format' not in twitchsettings:
            twitchsettings['format'] = '!editcom {command} Blinds: {blinds} {blindtimes} | End Enters: {ees} {eetimes} | Completions: {completions} {completiontimes}'
            
        if 'command' not in twitchsettings:
            twitchsettings['command'] = input('What twitch command should be updated? (leave blank for "!today") ') or "!today"

        print("Enabling twitch integration...")
        
        self.twitch = await Twitch('cy0wkkzf69rj7gsvypb6tjxdvdoif3', authenticate_app=False)
        self.twitch.auto_refresh_auth = False

        scope = [AuthScope.CHAT_READ, AuthScope.CHAT_EDIT]
        auth = ImplicitAuthenticator(self.twitch, scope, force_verify=False)
        try:
            token = await auth.authenticate()
        except TwitchAPIException as e:
            print('Error authenticating with Twitch: {}'.format(e))
            return
        await self.twitch.set_user_authentication(token, scope)

        thisuser = await first(self.twitch.get_users())

        self.chat = await Chat(self.twitch)
        self.room = thisuser.login

    async def update_command(self):
        if self.dirty:
            self.chat.start()
            await self.chat.join_room(self.room)
            await self.chat.send_message(self.room, self.get_update_command())
            await self.chat.leave_room(self.room)
            self.chat.stop()
            self.dirty = False
            
    def get_update_command(self):
        command = self.settings['twitch']['command']
        format = self.settings['twitch']['format']
        
        return format.format(
            command=command,
            blinds=self.blinds[0], 
            sub4=self.blinds[1], 
            sub330=self.blinds[2], 
            sub3=self.blinds[3], 
            ees=self.ees, 
            completions=self.completions, 
            blindtimes=tostring(self.blindtimes), 
            eetimes=tostring(self.eetimes),
            completiontimes=tostring(self.completiontimes)
        )

    async def stop(self):
        pass
