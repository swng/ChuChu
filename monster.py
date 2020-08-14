# everything here is complete bullshit

from enum import Enum

import urllib.request

PORTRAIT_URL = 'http://puzzledragonx.com/en/img/book/'

# dict of aliases
aliases = \
{
    "supergirl": 1678,
    "yukari": 2119,
    "lucia": 6210,
    "indra": 5940,
    "nohime": 6361,
    "aljae": 6159
}

def stringSearch(query):
    
    query = query.strip().lower()
    
    if query in aliases: return aliases[query]
    
    return None

def monster_exists(monster_no):
    """
    Checks that a sample monter exists on padx.
    :rtype: bool
    """
    request = urllib.request.Request(PORTRAIT_URL + monster_no + '.png')
    request.get_method = lambda: 'HEAD'

    try:
        urllib.request.urlopen(request)
        return True
    except urllib.request.HTTPError:
        return False

class fakeAwakening():
    def __init__(self):
        self.abc = 2 # wtf are you even doing
        

class Attribute(Enum):
    """Standard 5 PAD colors in enum form. Values correspond to DadGuide values."""
    Fire = 0
    Water = 1
    Wood = 2
    Light = 3
    Dark = 4


class MonsterType(Enum):
    Evolve = 0
    Balance = 1
    Physical = 2
    Healer = 3
    Dragon = 4
    God = 5
    Attacker = 6
    Devil = 7
    Machine = 8
    Awoken = 12
    Enhance = 14
    Vendor = 15


class EvoType(Enum):
    """Evo types supported by DadGuide. Numbers correspond to their id values."""
    Base = 0  # Represents monsters who didn't require evo
    Evo = 1
    UvoAwoken = 2
    UuvoReincarnated = 3

class Monster(): # fake
    # pepega
    def __init__(self, id_num):
        self.monster_id = id_num # yes everything about this is fake as shit
        self.monster_no_na = id_num
        self.monster_no_jp = id_num
        
        self.types = [MonsterType(1)] # 1 should be Bal type to allow for any latent killer I guess
        self.active_skill = True
        
        self.limit_mult = 10 # ? idk what this does
        
        self.level = 99 # ?
        
        self.in_pem = True # pepega
        self.in_rem = True # mmmmmmmm

        self.awakenings = [fakeAwakening(), fakeAwakening(), fakeAwakening(), fakeAwakening(), fakeAwakening(), fakeAwakening(), fakeAwakening(), fakeAwakening(), fakeAwakening(), fakeAwakening(), fakeAwakening(), fakeAwakening]
        self.superawakening_count = 3 # lies

        self.is_inheritable = True # mmmmm

        self.evo_from = self # yeah sure this makes total sense

        self.is_equip = True # I guess

        base_id = self.monster_id
        next_base = self.monster_id # lies, idk
        
        self._base_monster_id = base_id

def findMonster(query):
    if query.isdigit():
        # m = self.monster_no_na_to_named_monster.get(int(query))
        if monster_exists(query):
            return Monster(int(query)), None, "ID lookup"
        else:
            return None, 'Monster not found', None
    
    sS = stringSearch(query)
    
    if sS != None: return Monster(sS), None, "ID lookup"
    
    return None, 'Monster not found', None
        
