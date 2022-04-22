"""Main RCPL module."""
import importlib
import shlex
import subprocess
from pathlib import Path
from pprint import pprint

import dotsi
import yaml
from prompt_toolkit import prompt
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.lexers import PygmentsLexer
from prompt_toolkit.styles import style_from_pygments_cls
from pygments.styles import get_style_by_name
import shutil


MODULE_PATH = Path(__file__).parent
SOURCE_DIR = Path('/tmp/rcpl')


class PartialFormatDict(dict):
    def __missing__(self, key):
        return f'{{{key}}}'


def check_bracketed_expression(pairings, brackets, user_input) -> str:
    """Return an unmatched bracket in the expression if any.

    This isn't strict, expressions like "{( })" are valid.
    TODO: Fix that.
    """
    try:
        for char in user_input:
            for pair in pairings:
                left, right = pair
                if char in pair:
                    brackets.append(char)
                    break
            else:
                continue

            if char == right:
                brackets.pop()
                _brackets = []
                while (popped := brackets.pop()) != left:
                    _brackets.append(popped)
                brackets.extend(_brackets)
    except IndexError:
        return char
    return None


def get_compile_command(config, source_file, output_file, **kwargs):
    partial_format_dict = PartialFormatDict(source_file=source_file,
                                            output_file=output_file,
                                            **config.compile_args)
    compile_command = config.compile_command.format_map(partial_format_dict)
    compile_command = compile_command.format_map(kwargs)
    return compile_command


def get_run_command(config, output_file, **kwargs):
    partial_format_dict = PartialFormatDict(output_file=output_file,
                                            **config.run_args)
    run_command = config.run_command.format_map(partial_format_dict)
    run_command = run_command.format_map(kwargs)
    return run_command


def compile(config, preamble, code, source_file, output_file) -> bool:
    """Compile the code!"""
    source = config.template.format(preamble=preamble, code=code)
    source_file.write_text(source)
    compile_command = get_compile_command(config, source_file=source_file, output_file=output_file)
    return subprocess.run(shlex.split(compile_command))


def execute(config, output_file, **kwargs):
    run_command = get_run_command(config, output_file)
    return subprocess.run(shlex.split(run_command), capture_output=True, text=True)


def remove_old_characters(state, output):
    output = output[state.character_count:]
    state.character_count += len(output)
    return output


def run():
    config_path = Path(MODULE_PATH, 'configs', 'cc.yaml')
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    config = dotsi.Dict(config)  # To make everything dot accessible

    bindings = KeyBindings()
    history = InMemoryHistory()
    lexer_module = importlib.import_module(config.prompt.lexer_module)
    lexer_class = getattr(lexer_module, config.prompt.lexer_class)

    @bindings.add('tab')
    def _(event):
        """tabs are just four spaces."""
        event.app.current_buffer.insert_text('    ')

    @bindings.add('c-r')
    def _(event):
        """Restart the prompt."""
        print('Restarting...')
        init(hard=True)
        event.app.current_buffer.reset()
        event.app.current_buffer.accept_handler(event.app.current_buffer)

    state = dotsi.Dict()

    def prompt_message():
        """Return the current prompt."""
        if state.inline:
            return ''
        return 'rcpl> '

    def init(hard=False):
        nonlocal state
        if hard:
            state.code_instructions = []
            state.preamble_instructions = []
        state.inline = False
        state.brackets = []
        state.current_instruction = []
        state.character_count = 0
    init(hard=True)

    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    unique_name = f'_{hash(" ")}'
    source_file = Path(SOURCE_DIR, unique_name).with_suffix(config.source_suffix)
    output_file = Path(SOURCE_DIR, unique_name)

    while True:
        try:
            user_input = prompt(message=prompt_message,
                                key_bindings=bindings,
                                lexer=PygmentsLexer(lexer_class),
                                style=style_from_pygments_cls(get_style_by_name('native')),
                                history=history)
        except KeyboardInterrupt:
            init()
            continue
        except EOFError:
            break

        if user_input == '':
            state.code_instructions.append('')
            continue

        if (char := check_bracketed_expression(config.prompt.pairings, state.brackets, user_input)) is not None:
            print(f'Unmatched {char}. Ignoring instruction')
            init()
            continue

        state.inline = True if state.brackets else False
        state.current_instruction.append(user_input)

        if not state.inline:
            instruction = '\n'.join(state.current_instruction)

            code_instructions = state.code_instructions.copy()
            preamble_instructions = state.preamble_instructions.copy()

            if instruction.startswith(config.prompt.preamble_start_char) and instruction.endswith(config.prompt.preamble_end_char):
                preamble_instructions += [instruction[1:-1]]
            else:
                code_instructions += [instruction]

            state.current_instruction = []

            preamble = '\n'.join(preamble_instructions)
            code = '\n'.join(code_instructions)

            completed_process = compile(config, preamble, code, source_file, output_file)
            if completed_process.returncode != 0:
                continue

            completed_process = execute(config, output_file)
            if completed_process.returncode != 0:
                continue

            output = completed_process.stdout
            output = remove_old_characters(state, output)

            if output:
                if output[-1] == '\n':
                    print(output[:-1])
                else:
                    print(output)

            state.preamble_instructions = preamble_instructions
            state.code_instructions = code_instructions

    shutil.rmtree(SOURCE_DIR)
