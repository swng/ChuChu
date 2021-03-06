import discord
from discord.ext import commands
from enum import Enum
import monster
import math
import csv
import os
import io
from shutil import rmtree
import re
import urllib

import aiohttp
from ply import lex
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from PIL import ImageChops

import json
import sys
from pathlib import Path

TOKEN = 'abc'

client = commands.Bot(command_prefix='.')

HELP_MSG = """
^buildimg <build_shorthand>
Generates an image representing a team based on a string.
Format:
    card name(assist)[latent,latent]*repeat|Stats
    Card name must be first, otherwise the order does not matter
    Separate each card with /
    Separate each team with ;
    To use / in card name, put quote around the entire team slot (e.g. "g/l medjed(g/x zela)"/...)
    sdr is a special card name for dummy assists/skill delay buffers
Latent Acronyms:
    Separate each latent with a ,
    Killers: bak(balanced), phk(physical), hek(healer), drk(dragon), gok(god), aak(attacker, dek(devil), mak(machine)
             evk(evo mat), rek(redeemable), awk(awoken mat), enk(enhance)
    Stats (+ for 2 slot): hp, atk, rcv, all(all stat), hp+, atk+, rcv+
    Resists (+ for 2 slot): rres, bres, gres, lres, dres, rres+, bres+, gres+, lres+, dres+
    Others: sdr, ah(autoheal)
Repeat:
    *# defines number of times to repeat this particular card
    e.g. whaledor(plutus)*3/whaledor(carat)*2 creates a team of 3 whaledor(plutus) followed by 2 whaledor(carat)
    Latents can also be repeated, e.g. whaledor[sdr*5] for 5 sdr latents
Stats Format:
    | LV### SLV## AW# SA# +H## +A## +R## +(0 or 297)
    | indicates end of card name and start of stats
    LV: level, 1 to 110
    SLV: skill level, 1 to 99 or MAX
    AW: awakenings, 0 to 9
    SA: super awakening, 0 to 9
    +H: HP plus, 0 to 99
    +A: ATK plus, 0 to 99
    +R: RCV plus, 0 to 99
    +: total plus (+0 or +297 only)
    Case insensitive, order does not matter
"""

"""
Examples:
1P:
    bj(weld)lv110/baldin[gok, gok, gok](gilgamesh)/youyu(assist reeche)/mel(chocolate)/isis(koenma)/bj(rathian)
2P:
    amen/dios(sdr) * 3/whaledor; mnoah(assist jack frost) *3/tengu/tengu[sdr,sdr,sdr,sdr,sdr,sdr](durandalf)
3P:
    zela(assist amen) *3/base raizer * 2/zela; zela(assist amen) *4/base valeria/zela; zela * 6
Latent Validation:
    eir[drk,drk,sdr]/eir[bak,bak,sdr]
Stats Validation:
    dmeta(uruka|lv110+297slvmax)|+h33+a66+r99lv110slv15/    hmyne(buruka|lv110+297slv1)|+h99+a99+r99lv110slv15
"""

MAX_LATENTS = 8
LATENTS_MAP = {
    1: 'bak',
    2: 'phk',
    3: 'hek',
    4: 'drk',
    5: 'gok',
    6: 'aak',
    7: 'dek',
    8: 'mak',
    9: 'evk',
    10: 'rek',
    11: 'awk',
    12: 'enk',
    13: 'all',
    14: 'hp+',
    15: 'atk+',
    16: 'rcv+',
    17: 'rres+',
    18: 'bres+',
    19: 'gres+',
    20: 'lres+',
    21: 'dres+',
    22: 'hp',
    23: 'atk',
    24: 'rcv',
    25: 'rres',
    26: 'bres',
    27: 'gres',
    28: 'lres',
    29: 'dres',
    30: 'ah',
    31: 'sdr',
    32: 'te',
    33: 'te+'
}
REVERSE_LATENTS_MAP = {v: k for k, v in LATENTS_MAP.items()}
TYPE_TO_KILLERS_MAP = {
    'God': [7],  # devil
    'Devil': [5],  # god
    'Machine': [5, 1],  # god balanced
    'Dragon': [8, 3],  # machine healer
    'Physical': [8, 3],  # machine healer
    'Attacker': [7, 2],  # devil physical
    'Healer': [4, 6],  # dragon attacker
}

AWK_CIRCLE = 'circle'
AWK_STAR = 'star'
DELAY_BUFFER = 'delay_buffer'
REMOTE_ASSET_URL = 'https://github.com/Mushymato/pdchu-cog/raw/master/assets/'
REMOTE_AWK_URL = 'https://f002.backblazeb2.com/file/dadguide-data/media/awakenings/{0:03d}.png'
# REMOTE_LAT_URL = 'https://pad.protic.site/wp-content/uploads/pad-latents/'

PORTRAIT_URL = 'http://puzzledragonx.com/en/img/book/'
#PORTRAIT_URL = 'https://f002.backblazeb2.com/file/miru-data/padimages/jp/portrait/'
PORTRAIT_DIR = './pad-portrait/'

def download_portrait(monster_no):
    monster_no = str(monster_no)
    p = Path(PORTRAIT_DIR)
    
    if p.exists():
        if p.is_dir():
            p = Path(PORTRAIT_DIR + monster_no + '.png')
            if p.exists():
                return False
        else:
            print(PORTRAIT_DIR + ' taken, cannot create folder')
            return False
    else:
        p.mkdir()
        print('Created ' + PORTRAIT_DIR)
    urllib.request.urlretrieve(PORTRAIT_URL + monster_no + '.png', PORTRAIT_DIR + monster_no + '.png')
    print('Downloaded ' + monster_no + '.png')


def outline_text(draw, x, y, font, text_color, text):
    shadow_color = 'black'
    draw.text((x - 1, y - 1), text, font=font, fill=shadow_color)
    draw.text((x + 1, y - 1), text, font=font, fill=shadow_color)
    draw.text((x - 1, y + 1), text, font=font, fill=shadow_color)
    draw.text((x + 1, y + 1), text, font=font, fill=shadow_color)
    draw.text((x, y), text, font=font, fill=text_color)


def generate_instructions(build): # bot command has no ability to call this but technically you can use write instructions manually
    output = ''
    for step in build['Instruction']:
        output += 'F{:d}: P{:d} '.format(step['Floor'], step['Player'])
        if step['Active'] is not None:
            output += ' '.join([str(build['Team'][idx][ids]['ID'])
                                for idx, side in enumerate(step['Active'])
                                for ids in side]) + ', '
        output += step['Action']
        output += '\n'
    return output


def trim(im):
    bg = Image.new(im.mode, im.size, (255, 255, 255, 0))
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        return im.crop(bbox)


def filename(name):
    keep_characters = ('.', '_')
    return "".join(c for c in name if c.isalnum() or c in keep_characters).rstrip()


def text_center_pad(font_size, line_height):
    return math.floor((line_height - font_size) / 2)


def idx_to_xy(idx):
        return idx // 2, (idx + 1) % 2

def validate_latents(latents, card_types): # useless because no database
    if latents is None:
        return None
    if card_types is None:
        return None
    if 'Balance' in card_types:
        return latents
    for idx, l in enumerate(latents):
        if 0 < l < 9:
            if not any([l in TYPE_TO_KILLERS_MAP[t] for t in card_types if t is not None]):
                latents[idx] = None
    latents = [l for l in latents if l is not None]
    return latents if len(latents) > 0 else None

class DictWithAttributeAccess(dict):
    def __getattr__(self, key):
        return self[key]

    def __setattr__(self, key, value):
        self[key] = value

def lstripalpha(s):
    while s and not s[0].isdigit():
        s=s[1:]
    return s

class PaDTeamLexer(object):
    tokens = [
        'ID',
        'ASSIST',
        'LATENT',
        'STATS',
        'SPACES',
        'LV',
        'SLV',
        'AWAKE',
        'SUPER',
        'P_HP',
        'P_ATK',
        'P_RCV',
        'P_ALL',
        'REPEAT',
    ]

    def t_ID(self, t):
        r'^.+?(?=[\(\|\[\*])|^(?!.*[\(\|\[\*].*).+'
        # first word before ( or [ or | or * entire word if those characters are not in string
        t.value = t.value.strip()
        return t

    def t_ASSIST(self, t):
        r'\(.*?\)'
        # words in ()
        t.value = t.value.strip('()')
        return t

    def t_LATENT(self, t):
        r'\[.+?\]'
        # words in []
        t.value = [l.strip().lower() for l in t.value.strip('[]').split(',')]
        for v in t.value.copy():
            if '*' not in v:
                continue
            tmp = [l.strip() for l in v.split('*')]
            if len(tmp[0]) == 1 and tmp[0].isdigit():
                count = int(tmp[0])
                latent = tmp[1]
            elif len(tmp[1]) == 1 and tmp[1].isdigit():
                count = int(tmp[1])
                latent = tmp[0]
            else:
                continue
            idx = t.value.index(v)
            t.value.remove(v)
            for i in range(count):
                t.value.insert(idx, latent)
        t.value = t.value[0:MAX_LATENTS]
        t.value = [REVERSE_LATENTS_MAP[l] for l in t.value if l in REVERSE_LATENTS_MAP]
        return t

    def t_STATS(self, t):
        r'\|'
        pass

    def t_SPACES(self, t):
        r'\s'
        # spaces must be checked after ID
        pass

    def t_LV(self, t):
        r'[lL][vV][lL]?\s?\d{1,3}'
        # LV followed by 1~3 digit number
        t.value = int(lstripalpha(t.value[2:]))
        return t

    def t_SLV(self, t):
        r'[sS][lL][vV]\s?(\d{1,2}|[mM][aA][xX])'
        # SL followed by 1~2 digit number or max
        t.value = t.value[3:]
        if t.value.isdigit():
            t.value = int(t.value)
        else:
            t.value = 99
        return t

    def t_AWAKE(self, t):
        r'[aA][wW]\s?\d'
        # AW followed by 1 digit number
        t.value = int(t.value[2:])
        return t

    def t_SUPER(self, t):
        r'[sS][aA]\s?\d'
        # SA followed by 1 digit number
        t.value = int(t.value[2:])
        return t

    def t_P_ALL(self, t):
        r'\+\s?\d{1,3}'
        # + followed by 0 or 297
        t.value = min(int(t.value[1:]), 297)
        return t

    def t_P_HP(self, t):
        r'\+[hH]\s?\d{1,2}'
        # +H followed by 1~2 digit number
        t.value = int(t.value[2:])
        return t

    def t_P_ATK(self, t):
        r'\+[aA]\s?\d{1,2}'
        # +A followed by 1~2 digit number
        t.value = int(t.value[2:])
        return t

    def t_P_RCV(self, t):
        r'\+[rR]\s?\d{1,2}'
        # +R followed by 1~2 digit number
        t.value = int(t.value[2:])
        return t

    def t_REPEAT(self, t):
        r'\*\s?\d'
        # * followed by a number
        t.value = min(int(t.value[1:]), MAX_LATENTS)
        return t

    t_ignore = '\t\n'

    def t_error(self, t):
        raise commands.UserFeedbackCheckFailure("Parse Error: Unknown text '{}' at position {}".format(t.value, t.lexpos))

    def build(self, **kwargs):
        # pass debug=1 to enable verbose output
        self.lexer = lex.lex(module=self)
        return self.lexer

class PadBuildImageGenerator(object):
    def __init__(self, params, build_name='pad_build'):
        self.params = params
        self.lexer = PaDTeamLexer().build()
        self.build = {
            'NAME': build_name,
            'TEAM': [],
            'INSTRUCTION': None
        }
        self.build_img = None

    def process_build(self, input_str):
        team_strings = [row for row in csv.reader(re.split('[;\n]', input_str), delimiter='/') if len(row) > 0]
        if len(team_strings) > 3:
            team_strings = team_strings[0:3]
        for team in team_strings:
            team_sublist = []
            for slot in team:
                try:
                    team_sublist.extend(self.process_card(slot))
                except Exception as ex:
                    self.build['TEAM'] = []
                    raise ex
            self.build['TEAM'].append(team_sublist)

    def process_card(self, card_str, is_assist=False):
        if not is_assist:
            result_card = {
                '+ATK': 99,
                '+HP': 99,
                '+RCV': 99,
                'AWAKE': 9,
                'SUPER': 0,
                'MAX_AWAKE': 9,
                'GOLD_STAR': True,
                'ID': 0,
                'LATENT': None,
                'LV': 99,
                'SLV': 0,
                'ON_COLOR': True
            }
        else:
            result_card = {
                '+ATK': 0,
                '+HP': 0,
                '+RCV': 0,
                'AWAKE': 0,
                'SUPER': 0,
                'MAX_AWAKE': 0,
                'GOLD_STAR': True,
                'ID': 0,
                'LATENT': None,
                'LV': 1,
                'SLV': 0,
                'MAX_SLV': 0,
                'ON_COLOR': False
            }
        if len(card_str) == 0:
            if is_assist:
                result_card['ID'] = DELAY_BUFFER
                return result_card, None
            else:
                return []
        self.lexer.input(card_str)
        assist_str = None
        card = None
        repeat = 1
        for tok in iter(self.lexer.token, None):
            # print('{} - {}'.format(tok.type, tok.value))
            if tok.type == 'ASSIST':
                assist_str = tok.value
            elif tok.type == 'REPEAT':
                repeat = min(tok.value, MAX_LATENTS)
            elif tok.type == 'ID':
                if tok.value.lower() == 'sdr':
                    result_card['ID'] = DELAY_BUFFER
                    card = DELAY_BUFFER
                else:
                    card, err, debug_info = monster.findMonster(tok.value)
                    if card is None:
                        print(err)
                        raise commands.UserFeedbackCheckFailure('Lookup Error: {}'.format(err)) # fix this
                    if not card.is_inheritable:
                        if is_assist:
                            return None, None
                        else:
                            result_card['GOLD_STAR'] = False
                    result_card['MNO'] = card.monster_no_na if card.monster_no_na != card.monster_id else card.monster_no_jp
                    result_card['ID'] = card.monster_id
            elif tok.type == 'P_ALL':
                if tok.value >= 297:
                    result_card['+HP'] = 99
                    result_card['+ATK'] = 99
                    result_card['+RCV'] = 99
                else:
                    result_card['+HP'] = 0
                    result_card['+ATK'] = 0
                    result_card['+RCV'] = 0
            elif tok.type != 'STATS':
                result_card[tok.type.replace('P_', '+')] = tok.value
        card_att = None
        if card is None:
            return []
        elif card != DELAY_BUFFER:
            result_card['LATENT'] = validate_latents(
                result_card['LATENT'],
                [t.name for t in card.types]
            )
            #result_card['LV'] = min(
            #    result_card['LV'],
            #    110 if card.limit_mult is not None and card.limit_mult > 1 else card.level
            #)
            
            if True: # card.active_skill: no database to look up skill information so
                result_card['MAX_SLV'] = 99 # card.active_skill.turn_max - card.active_skill.turn_min + 1
            else:
                result_card['MAX_SLV'] = 0
            result_card['MAX_AWAKE'] = len(card.awakenings) - card.superawakening_count
            if is_assist:
                result_card['MAX_AWAKE'] = result_card['MAX_AWAKE'] if result_card['AWAKE'] > 0 else 0
                result_card['AWAKE'] = result_card['MAX_AWAKE']
                result_card['SUPER'] = 0
            else:
                result_card['SUPER'] = min(result_card['SUPER'], card.superawakening_count)
                if result_card['SUPER'] > 0:
                    super_awakes = [x.awoken_skill_id for x in card.awakenings[-card.superawakening_count:]]
                    result_card['SUPER'] = super_awakes[result_card['SUPER'] - 1]
                    result_card['LV'] = max(100, result_card['LV'])
            # card_att = card.attr1 # let's comment this out because why does attribute matter
        if is_assist:
            return result_card, card_att
        else:
            parsed_cards = [result_card]
            if isinstance(assist_str, str):
                assist_card, assist_att = self.process_card(assist_str, is_assist=True)
                if card_att is not None and assist_att is not None:
                    assist_card['ON_COLOR'] = card_att == assist_att
                parsed_cards.append(assist_card)
            else:
                parsed_cards.append(None)
            parsed_cards = parsed_cards * repeat
            return parsed_cards

    def combine_latents(self, latents):
        if not latents:
            return False
        if len(latents) > MAX_LATENTS:
            latents = latents[0:MAX_LATENTS]
        latents_bar = Image.new('RGBA',
                                (self.params.PORTRAIT_WIDTH, self.params.LATENTS_WIDTH * 2),
                                (255, 255, 255, 0))
        x_offset = 0
        y_offset = 0
        row_count = 0
        one_slot, two_slot = [], []
        for l in latents:
            if l < 22:
                two_slot.append(l)
            else:
                one_slot.append(l)
        sorted_latents = []
        if len(one_slot) > len(two_slot):
            sorted_latents.extend(one_slot)
            sorted_latents.extend(two_slot)
        else:
            sorted_latents.extend(two_slot)
            sorted_latents.extend(one_slot)
        last_height = 0
        for l in sorted_latents:
            latent_icon = Image.open(self.params.ASSETS_DIR + 'lat/' + LATENTS_MAP[l] + '.png')
            if x_offset + latent_icon.size[0] > self.params.PORTRAIT_WIDTH:
                row_count += 1
                x_offset = 0
                y_offset += last_height
            if row_count >= MAX_LATENTS//4 and x_offset + latent_icon.size[0] >= self.params.LATENTS_WIDTH * (MAX_LATENTS%4):
                break
            latents_bar.paste(latent_icon, (x_offset, y_offset))
            last_height = latent_icon.size[1]
            x_offset += latent_icon.size[0]

        return latents_bar

    def combine_portrait(self, card, show_stats=True, show_supers=False):
        if card['ID'] == DELAY_BUFFER:
            return Image.open(self.params.ASSETS_DIR + DELAY_BUFFER + '.png')
        #if 'http' in self.params.PORTRAIT_DIR:
        #    portrait = Image.open(urllib.request.urlopen(self.params.PORTRAIT_DIR.format(monster_id=card['ID'])))
        else:
            download_portrait(card['ID'])
            portrait = Image.open(self.params.PORTRAIT_DIR + str(card['ID']) + '.png')
        draw = ImageDraw.Draw(portrait)
        slv_offset = 80
        if show_stats:
            # + eggsinclude_instructions
            sum_plus = card['+HP'] + card['+ATK'] + card['+RCV']
            if 0 < sum_plus:
                if sum_plus < 297:
                    font = ImageFont.truetype(self.params.FONT_NAME, 14)
                    outline_text(draw, 5, 2, font, 'yellow', '+{:d} HP'.format(card['+HP']))
                    outline_text(draw, 5, 14, font, 'yellow', '+{:d} ATK'.format(card['+ATK']))
                    outline_text(draw, 5, 26, font, 'yellow', '+{:d} RCV'.format(card['+RCV']))
                else:
                    font = ImageFont.truetype(self.params.FONT_NAME, 18)
                    outline_text(draw, 5, 2, font, 'yellow', '+297')
            # level
            if card['LV'] > 0:
                outline_text(draw, 5, 75, ImageFont.truetype(self.params.FONT_NAME, 18),
                             'white', 'Lv.{:d}'.format(card['LV']))
                slv_offset = 65
        # skill level
        if card['MAX_SLV'] > 0 and card['SLV'] > 0:
            slv_txt = 'SLv.max' if card['SLV'] >= card['MAX_SLV'] else 'SLv.{:d}'.format(card['SLV'])
            outline_text(draw, 5, slv_offset,
                         ImageFont.truetype(self.params.FONT_NAME, 12), 'pink', slv_txt)
        # ID
        outline_text(draw, 67, 82, ImageFont.truetype(self.params.FONT_NAME, 12), 'lightblue', str(card['MNO']))
        del draw
        if card['MAX_AWAKE'] > 0:
            # awakening
            if card['AWAKE'] >= card['MAX_AWAKE']:
                awake = Image.open(self.params.ASSETS_DIR + AWK_STAR + '.png')
            else:
                awake = Image.open(self.params.ASSETS_DIR + AWK_CIRCLE + '.png')
                draw = ImageDraw.Draw(awake)
                draw.text((8, -2), str(card['AWAKE']),
                          font=ImageFont.truetype(self.params.FONT_NAME, 18), fill='yellow')
                del draw
            portrait.paste(awake, (self.params.PORTRAIT_WIDTH - awake.size[0] - 5, 5), awake)
            awake.close()
        #if show_supers and card['SUPER'] > 0:
            # SA
        #    awake = Image.open(self.params.ASSETS_DIR + 'awk/' + str(card['SUPER']) + '.png')
        #    portrait.paste(awake,
        #                   (self.params.PORTRAIT_WIDTH - awake.size[0] - 5,
        #                    (self.params.PORTRAIT_WIDTH - awake.size[0]) // 2),
        #                   awake)
        #    awake.close()
        return portrait

    def generate_build_image(self, include_instructions=False):
        if self.build is None:
            return
        team_size = max([len(x) for x in self.build['TEAM']])
        p_w = self.params.PORTRAIT_WIDTH * math.ceil(team_size / 2) + \
              self.params.PADDING * math.ceil(team_size / 10)
        p_h = (self.params.PORTRAIT_WIDTH * 2 + self.params.LATENTS_WIDTH + self.params.PADDING) * \
              2 * len(self.build['TEAM'])
        include_instructions &= self.build['INSTRUCTION'] is not None
        if include_instructions:
            p_h += len(self.build['INSTRUCTION']) * (self.params.PORTRAIT_WIDTH // 2 + self.params.PADDING)
        self.build_img = Image.new('RGBA',
                                   (p_w, p_h),
                                   (255, 255, 255, 0))
        y_offset = 0
        for team in self.build['TEAM']:
            has_assist = any([card is not None for idx, card in enumerate(team) if idx % 2 == 1])
            has_latents = any([card['LATENT'] is not None for idx, card in enumerate(team)
                               if idx % 2 == 0 and card is not None])
            if has_assist:
                y_offset += self.params.PORTRAIT_WIDTH
            for idx, card in enumerate(team):
                if idx > 11 or idx > 9 and len(self.build['TEAM']) % 2 == 0:
                    break
                if card is not None:
                    x, y = idx_to_xy(idx)
                    portrait = self.combine_portrait(
                        card,
                        show_stats=card['ON_COLOR'],
                        show_supers=len(self.build['TEAM']) == 1)
                    if portrait is None:
                        continue
                    x_offset = self.params.PADDING * math.ceil(x / 4)
                    self.build_img.paste(
                        portrait,
                        (x_offset + x * self.params.PORTRAIT_WIDTH,
                         y_offset + y * self.params.PORTRAIT_WIDTH))
                    if has_latents and idx % 2 == 0 and card['LATENT'] is not None:
                        latents = self.combine_latents(card['LATENT'])
                        self.build_img.paste(
                            latents,
                            (x_offset + x * self.params.PORTRAIT_WIDTH,
                             y_offset + (y + 1) * self.params.PORTRAIT_WIDTH))
                        latents.close()
                    portrait.close()
            y_offset += self.params.PORTRAIT_WIDTH + self.params.PADDING * 2
            if has_latents:
                y_offset += self.params.LATENTS_WIDTH * 2

        if include_instructions:
            y_offset -= self.params.PADDING * 2
            draw = ImageDraw.Draw(self.build_img)
            font = ImageFont.truetype(self.params.FONT_NAME, 24)
            text_padding = text_center_pad(25, self.params.PORTRAIT_WIDTH // 2)
            for step in self.build['INSTRUCTION']:
                x_offset = self.params.PADDING
                outline_text(draw, x_offset, y_offset + text_padding,
                             font, 'white', 'F{:d} - P{:d} '.format(step['FLOOR'], step['PLAYER'] + 1))
                x_offset += self.params.PORTRAIT_WIDTH
                if step['ACTIVE'] is not None:
                    actives_used = [self.build['TEAM'][idx][ids]
                                    for idx, side in enumerate(step['ACTIVE'])
                                    for ids in side]
                    for card in actives_used:
                        if 'http' in self.params.PORTRAIT_DIR:
                            p_small = Image.open(urllib.request.urlopen(self.params.PORTRAIT_DIR.format(monster_id=card['ID']))).resize((self.params.PORTRAIT_WIDTH // 2, self.params.PORTRAIT_WIDTH // 2), Image.LINEAR)
                        else:
                            p_small = Image.open(self.params.PORTRAIT_DIR.format(monster_id=card['ID'])).resize((self.params.PORTRAIT_WIDTH // 2, self.params.PORTRAIT_WIDTH // 2), Image.LINEAR)
                        self.build_img.paste(p_small, (x_offset, y_offset))
                        x_offset += self.params.PORTRAIT_WIDTH // 2
                    x_offset += self.params.PADDING
                outline_text(draw, x_offset, y_offset + text_padding, font, 'white', step['ACTION'])
                y_offset += self.params.PORTRAIT_WIDTH // 2
            del draw

        self.build_img = trim(self.build_img)
    



@client.command()
@commands.is_owner()
async def shutdown(ctx):
    await ctx.send("Shutting down")
    await ctx.bot.logout()

@client.event
async def on_message(message): # manually implementing the chuchu commands where the input is a string with whitespace, so you don't need to surround it with quotes.
    # we do not want the bot to reply to itself
    if message.author == client.user:
        return

    if message.content.startswith('!hello'):
        msg = 'Hello {0.author.mention}'.format(message)
        await message.channel.send(msg)
    
    if message.content.startswith('!chuchu'):
        
        msg = "Processing build".format(message)
        await message.channel.send(msg)
        
        try:
            params = DictWithAttributeAccess({
            'ASSETS_DIR': './assets/',
            'PORTRAIT_DIR': './pad-portrait/',
            'PORTRAIT_URL': 'http://puzzledragonx.com/en/img/book/',
            # 'PORTRAIT_DIR': 'https://f002.backblazeb2.com/file/dadguide-data/media/icons/{monster_id:05d}.png',
            'OUTPUT_DIR': './data/padbuildimg/output/',
            'PORTRAIT_WIDTH': 100,
            'PADDING': 10,
            'LATENTS_WIDTH': 25,
            # 'FONT_NAME': './assets/tf2build.ttf' # random sone I have on my comp...
            'FONT_NAME': './assets/OpenSans-ExtraBold.ttf'
        })
            pbg = PadBuildImageGenerator(params)
            # print('PARSE: {}'.format(time.perf_counter() - start))
            print(message.content[8:])
            pbg.process_build(message.content[8:])
            # print(pbg.build)
            # start = time.perf_counter()
            pbg.generate_build_image()
            # print('DRAW: {}'.format(time.perf_counter() - start))
        except: print('Something went wrong.')

        # start = time.perf_counter()
        if pbg.build_img is not None:
            with io.BytesIO() as build_io:
                pbg.build_img.save(build_io, format='PNG')
                build_io.seek(0)
                if False: # ctx.guild and self.settings.dmOnly(ctx.guild.id): ok so I don't wanna deal with this shit
                    try:
                        await ctx.author.send(file=discord.File(build_io,'pad_build.png'))
                        await ctx.send(inline('Sent build to {}'.format(ctx.author)))
                    except discord.errors.Forbidden as ex:
                        await ctx.send(inline('Failed to send build to {}'.format(ctx.author)))
                else:
                    await message.channel.send(file=discord.File(build_io, 'pad_build.png'))
                    # await ctx.send(file=discord.File(build_io,'pad_build.png'))
                    
        else:
            msg = "Invalid build".format(message)
            await message.channel.send(msg)
            
    if message.content.startswith('!cc'):
        msg = "Processing build.".format(message)
        await message.channel.send(msg)
 
        try:
            params = DictWithAttributeAccess({
            'ASSETS_DIR': './assets/',
            'PORTRAIT_DIR': './pad-portrait/',
            'PORTRAIT_URL': 'http://puzzledragonx.com/en/img/book/',
            # 'PORTRAIT_DIR': 'https://f002.backblazeb2.com/file/dadguide-data/media/icons/{monster_id:05d}.png',
            'OUTPUT_DIR': './data/padbuildimg/output/',
            'PORTRAIT_WIDTH': 100,
            'PADDING': 10,
            'LATENTS_WIDTH': 25,
            # 'FONT_NAME': './assets/tf2build.ttf' # random font I have on my comp...
            'FONT_NAME': './assets/OpenSans-ExtraBold.ttf'
        })
            pbg = PadBuildImageGenerator(params)
            # print('PARSE: {}'.format(time.perf_counter() - start))
            print(message.content[4:])
            pbg.process_build(message.content[4:])
            # print(pbg.build)
            # start = time.perf_counter()
            pbg.generate_build_image()
            # print('DRAW: {}'.format(time.perf_counter() - start))
        except: print('something went wrong')

        # start = time.perf_counter()
        if pbg.build_img is not None:
            with io.BytesIO() as build_io:
                pbg.build_img.save(build_io, format='PNG')
                build_io.seek(0)
                if False: # ctx.guild and self.settings.dmOnly(ctx.guild.id): ok so I don't wanna deal with this shit
                    try:
                        await ctx.author.send(file=discord.File(build_io,'pad_build.png'))
                        await ctx.send(inline('Sent build to {}'.format(ctx.author)))
                    except discord.errors.Forbidden as ex:
                        await ctx.send(inline('Failed to send build to {}'.format(ctx.author)))
                else:
                    await message.channel.send(file=discord.File(build_io, 'pad_build.png'))
                    # await ctx.send(file=discord.File(build_io,'pad_build.png'))
                    
        else:
            msg = "Invalid build".format(message)
            await message.channel.send(msg)
    
    await client.process_commands(message)


@client.event
async def on_ready():
    print('Logged in as')
    print(client.user.name)
    print(client.user.id)
    print('------')

client.run(TOKEN)
