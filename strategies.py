"""
Some example strategies for people who want to create a custom, homemade bot.
And some handy classes to extend
"""
import asyncio
import logging
import sys
from typing import Optional, Iterable

import chess
from chess.engine import PlayResult, Limit, Info, ConfigMapping, AnalysisResult
import random
from engine_wrapper import EngineWrapper


class FillerEngine:
    """
    Not meant to be an actual engine.

    This is only used to provide the property "self.engine"
    in "MinimalEngine" which extends "EngineWrapper"
    """
    def __init__(self, main_engine, name=None):
        self.id = {
            "name": name
        }
        self.name = name
        self.main_engine = main_engine

    def __getattr__(self, method_name):
        main_engine = self.main_engine

        def method(*args, **kwargs):
            nonlocal main_engine
            nonlocal method_name
            return main_engine.notify(method_name, *args, **kwargs)

        return method


class MinimalEngine(EngineWrapper):
    """
    Subclass this to prevent a few random errors

    Even though MinimalEngine extends EngineWrapper,
    you don't have to actually wrap an engine.

    At minimum, just implement `search`,
    however you can also change other methods like
    `notify`, `first_search`, `get_time_control`, etc.
    """
    def __init__(self, commands, options, stderr, draw_or_resign, name=None, **popen_args):
        super().__init__(options, draw_or_resign)

        self.engine_name = self.__class__.__name__ if name is None else name

        self.engine = FillerEngine(self, name=self.name)
        self.engine.id = {
            "name": self.engine_name
        }

    def search(self, board, time_limit, ponder, draw_offered):
        """
        The method to be implemented in your homemade engine

        NOTE: This method must return an instance of "chess.engine.PlayResult"
        """
        raise NotImplementedError("The search method is not implemented")

    def notify(self, method_name, *args, **kwargs):
        """
        The EngineWrapper class sometimes calls methods on "self.engine".
        "self.engine" is a filler property that notifies <self>
        whenever an attribute is called.

        Nothing happens unless the main engine does something.

        Simply put, the following code is equivalent
        self.engine.<method_name>(<*args>, <**kwargs>)
        self.notify(<method_name>, <*args>, <**kwargs>)
        """
        pass


class ExampleEngine(MinimalEngine):
    pass


# Strategy names and ideas from tom7's excellent eloWorld video

class RandomMove(ExampleEngine):
    def search(self, board, *args):
        return PlayResult(random.choice(list(board.legal_moves)), None)


class Alphabetical(ExampleEngine):
    def search(self, board, *args):
        moves = list(board.legal_moves)
        moves.sort(key=board.san)
        return PlayResult(moves[0], None)


class FirstMove(ExampleEngine):
    """Gets the first move when sorted by uci representation"""
    def search(self, board, *args):
        moves = list(board.legal_moves)
        moves.sort(key=str)
        return PlayResult(moves[0], None)


class CO456Protocol(chess.engine.Protocol):
    def __init__(self) -> None:
        super().__init__()
        self.first_move = ""

    async def initialize(self) -> None:
        class InitializeCommand(chess.engine.BaseCommand[CO456Protocol, None]):
            def check_initialized(self, engine: CO456Protocol) -> None:
                if engine.initialized:
                    raise chess.engine.EngineError("engine already initialized")

            def start(self, engine: CO456Protocol) -> None:
                logging.info("Initialized!")
                engine.initialized = True
                self.result.set_result(None)
                self.set_finished()

        return await self.communicate(InitializeCommand)

    async def ping(self) -> None:
        pass

    async def configure(self, options: ConfigMapping) -> str:
        class ConfigureCommand(chess.engine.BaseCommand[CO456Protocol, None]):
            def start(self, engine: CO456Protocol) -> None:
                if "color" in options:
                    engine.send_line(options.get("color"))
                    if options.get("color") == "black":
                        self.result.set_result(None)
                        self.set_finished()

            def line_received(self, engine: CO456Protocol, line: str) -> None:
                logging.info("CO456 Protocol received " + line)

                engine.first_move = line
                self.result.set_result(None)
                self.set_finished()

        return await self.communicate(ConfigureCommand)

    async def play(self, board: chess.Board, limit: Limit, *, game: object = None, info: Info = chess.engine.INFO_NONE,
                   ponder: bool = False, draw_offered: bool = False, root_moves: Optional[Iterable[chess.Move]] = None,
                   options: ConfigMapping = {}) -> PlayResult:
        class PlayCommand(chess.engine.BaseCommand[CO456Protocol, PlayResult]):
            def start(self, engine: CO456Protocol) -> None:
                if engine.first_move:
                    self.result.set_result(PlayResult(chess.Move.from_uci(engine.first_move), None))
                    engine.first_move = ""
                    self.set_finished()
                elif board.move_stack:
                    engine.send_line(board.move_stack[-1].uci())

            def line_received(self, engine: CO456Protocol, line: str) -> None:
                logging.info("CO456 Protocol received " + line)

                if line == "invalid":
                    self.result.set_result(PlayResult(next(iter(board.legal_moves)), None, resigned=True))
                else:
                    self.result.set_result(PlayResult(chess.Move.from_uci(line), None))
                self.set_finished()

        return await self.communicate(PlayCommand)

    async def analysis(self, board: chess.Board, limit: Optional[Limit] = None, *, multipv: Optional[int] = None,
                       game: object = None, info: Info = chess.engine.INFO_ALL,
                       root_moves: Optional[Iterable[chess.Move]] = None,
                       options: ConfigMapping = {}) -> AnalysisResult:
        pass

    async def quit(self) -> None:
        pass


# Strategy that bridges CO456 antichess API to lichess bot
class CO456Engine(EngineWrapper):
    # commands - cli command to run the executable
    # options - homemade_options in config.yml
    # stderr - subprocess.DEVNULL if silence_stderr is true in config
    # draw_or_resign - draw_or_resign options in config.yml
    # name - name of the executable
    # popen_args - cwd=working directory for the executable
    def __init__(self, commands, options, stderr, draw_or_resign, name=None, **popen_args):
        super().__init__(options, draw_or_resign)

        self.engine = chess.engine.SimpleEngine.popen(CO456Protocol, commands, stderr=stderr, **popen_args)

    # Get black or white from opponent info, which is called immediately after initialization
    def get_opponent_info(self, game):
        msg = "white" if game.is_white else "black"
        self.engine.configure({"color": msg})

    # Your turn!
    def search(self, board, time_limit, ponder, draw_offered):
        result = self.engine.play(board, time_limit)
        return result
