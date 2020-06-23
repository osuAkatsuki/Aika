from typing import Tuple, Union
from os import chdir, path
from subprocess import run, PIPE
from json import loads
from requests import get

import utils

# TODO: async
class Owoppai:
    def __init__(self) -> None:
        self.filename = ''
        self.accuracy = -1.0
        self.mods = 0
        self.combo = 0
        self.misses = 0
        self.gamemode = 0

        chdir(path.dirname(path.realpath(__file__)))

    def open_map(self, beatmap_id: int) -> None:
        filename = f'maps/{beatmap_id}.osu'
        if not path.exists(filename):
            # Do osu!api request for the map.
            if not (r := get(f'https://old.ppy.sh/osu/{beatmap_id}')):
                raise Exception(f'Could not find beatmap {filename}!')

            with open(filename, 'w+') as f:
                f.write(r.content.decode('utf-8', 'strict'))

        self.filename = filename

    def configure(self, **kwargs) -> None:
        if 'filename' in kwargs:
            self.open_map(kwargs.pop('filename'))

        self.gamemode = kwargs.pop('mode', 0)
        self.mods = kwargs.pop('mods', 0)
        self.combo = kwargs.pop('combo', 0)

        acc_args = { # std
            'n300', 'n100', 'n50', 'nmiss'} \
        if self.gamemode == 0 else { # taiko
            'n300', 'n150', 'nmiss'}

        if all(x in kwargs for x in acc_args):
            if self.gamemode == 0:
                self.accuracy = utils.calc_accuracy_std(**kwargs)
            else:
                self.accuracy = utils.calc_accuracy_taiko(**kwargs)
        else:
            self.accuracy = kwargs.get('accuracy', -1.0)

        self.misses = kwargs.get('misses', 0)

    def calculate_pp(self) -> Union[Tuple[float], float]:
        # This function can either return a list of
        # PP values, # or just a single PP value.
        if not self.filename: raise Exception(
            'Must open a map prior to calling calculate_pp()')

        args = [f'./oppai {self.filename}']
        if self.accuracy >= 0.0:
            args.append(f'{self.accuracy:.4f}%')
        if self.mods >= 0:
            args.append(f'+{utils.mods_readable(self.mods)}')
        if self.combo:
            args.append(f'{self.combo}x')
        if self.misses:
            args.append(f'{self.misses}m')
        if self.gamemode == 1: # taiko support
            args.append('-taiko')

        # Output in json format
        args.append('-ojson')

        process = run(
            ' '.join(args),
            shell = True, stdout = PIPE, stderr = PIPE)

        output = loads(process.stdout.decode('utf-8', errors='ignore'))

        important = ('code', 'errstr', 'pp', 'stars')
        if any(i not in output for i in important) or output['code'] != 200:
            raise Exception('Error while calculating PP')

        pp = output['pp']
        stars = output['stars']
        return pp, stars # TODO: test output type? is this a tuple?
