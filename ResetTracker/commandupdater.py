def ms_to_string(ms):
        time = int(ms) // 1000
        hr = time // 3600
        min = (time % 3600) // 60
        sec = time % 60
        res = ''
        if hr > 0:
            res += f'{hr}:'
        res += f'{min:02d}:' if hr > 0 else f'{min}:'
        res += f'{sec:02d}'
        return res

class CommandUpdater:
    """
    base class for twitch and nightbot command updater
    that keeps track of blind, ee, completion times and counts
    """
    
    def __init__(self, settings: dict):
        self.blinds = [0] * 4
        self.ees = 0
        self.completions = 0
        self.blindtimes = []
        self.eetimes = []
        self.completiontimes = []
        
        self.settings = settings
        self.dirty = False
    
    async def setup(self):
        pass
    
    async def update_command(self):
        """makes the request to update the command"""
        pass
    
    async def stop(self):
        pass
    

    def blind(self, time):
        """
        called when user gets a run that blinds at a time (in ms) 
        """
        self.blinds[0] += 1
        self.blindtimes.append(ms_to_string(time))
        self.dirty = True

    def enter_end(self, time):
        self.ees += 1
        self.eetimes.append(ms_to_string(time))
        self.dirty = True

    def completion(self, time):
        self.completions += 1
        self.completiontimes.append(ms_to_string(time))
        self.dirty = True

    def reset(self):
        self.blinds = [0] * 4
        self.ees = 0
        self.completions = 0
        self.blindtimes = []
        self.eetimes = []
        self.completiontimes = []
        self.dirty = True
        
    def updatecounter(self, counter, values):
        if counter == "blinds":
            self.blinds[0] = values[0]
        elif counter == "sub4":
            self.blinds[1] = values[0]
        elif counter == "sub330":
            self.blinds[2] = values[0]
        elif counter == "sub3":
            self.blinds[3] = values[0]
        elif counter == "ees":
            self.ees = values[0]
        elif counter == "completions":
            self.completions = values[0]
        elif counter == "blindtimes":
            self.blindtimes = values
        elif counter == "eetimes":
            self.eetimes = values
        elif counter == "completiontimes":
            self.completiontimes = values
        else:
            return False
        self.dirty = True
        return True
