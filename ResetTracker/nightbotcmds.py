
from commandupdater import CommandUpdater
from nightbotauth import Nightbot, AuthScope, NightbotImplAuthenticator

def tostring(list):
    if len(list) == 0:
        return ""
    return f"[{', '.join(list)}]"
    

class NightbotCommandUpdater(CommandUpdater):
    def __init__(self, settings):
        super().__init__(settings)
        self.nbot = None
    
    async def setup(self):
        # settings structure: 'twitch' has 'method' which is either 'chat' or 'nightbot' or something else
        # and also has 'format' and 'command'
        # assert self.settings['twitch']['method'] == 'nightbot'
        twitchsettings: dict = self.settings['twitch']
        if 'format' not in twitchsettings:
            twitchsettings['format'] = 'Blinds: {blinds} {blindtimes} | End Enters: {ees} {eetimes} | Completions: {completions} {completiontimes}'
        
        if 'command' not in twitchsettings:
            twitchsettings['command'] = input('What nightbot command should be updated? (leave blank for "!today") ') or "!today"

        print("Enabling nightbot integration...")

        self.nbot = Nightbot('3df83e4d6c9bfafc5c25f3f6669fe59f')
        scopes = [AuthScope.CHANNEL_SEND, AuthScope.COMMANDS]
    
        auth = NightbotImplAuthenticator(self.nbot, scopes)
        token = await auth.authenticate()
        await self.nbot.set_user_authentication(token, scopes)
        
    async def update_command(self):
        if self.dirty:
            await self.nbot.edit_command(self.settings['twitch']['command'], self.get_update_command())
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
        await self.nbot.stop()
