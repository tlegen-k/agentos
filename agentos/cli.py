"""AgentOS command line interface (CLI).

The CLI allows creation of a simple template agent.
"""
import agentos
import click
from datetime import datetime
import gym
import mlflow.projects
import importlib.util
from pathlib import Path


CONDA_ENV_FILE = Path("./conda_env.yaml")
CONDA_ENV_CONTENT = \
"""{file_header}

name: {name}

dependencies:
    - pip
    - pip: 
      - -e path/to/agentos/git/repo
      # ...or once we are in PyPi:
      #- agentos
      - gym
"""
MLFLOW_PROJECT_FILE = Path("./MLProject")
MLFLOW_PROJECT_CONTENT = \
"""{file_header}

name: {name}

conda_env: {conda_env}

entry_points:
  main:
    command: "python main.py"
"""
AGENT_DEF_FILE = Path("./agent.py")  # Default location of agent code.
AGENT_MAIN_FILE = Path("./main.py")
AGENT_MAIN = \
"""{file_header}
import agentos
import random
import gym

# TODO: REPLACE THE EXAMPLE CODE BELOW WITH YOUR OWN!

# A minimal 1D hallway env class.
class MyEnv(gym.Env):
    def __init__(self):
        super().__init__()
        self.l_r_pos = 0  # left is neg, right is pos.
        
    def reset(self):
        self.l_r_pos = 0
        return 0
    
    def step(self, action):
        self.l_r_pos += action
        return self.l_r_pos, abs(self.l_r_pos), False, dict()
        

# A minimal example agent class.
class MyAgent(agentos.Agent):
    def __init__(self, env_class):
        super().__init__(env_class)
        self.step_count = 0
    
    def advance(self):
        print("Taking step " + str(self.step_count))
        pos_in_env, _, _, _ = self.env.step(random.choice([-1,1]))
        print("Position in env is now: " + str(pos_in_env))
        self.step_count += 1


if __name__ == "__main__":
    agentos.run_agent(MyAgent, MyEnv, max_iters=5)
"""
INIT_FILES = {CONDA_ENV_FILE: CONDA_ENV_CONTENT,
              MLFLOW_PROJECT_FILE: MLFLOW_PROJECT_CONTENT,
              AGENT_MAIN_FILE: AGENT_MAIN}


@click.group()
def agentos_cmd():
    pass


def validate_agent_name(ctx, param, value):
    if ' ' in value or ':' in value or '/' in value:
        raise click.BadParameter("name may not contain ' ', ':', or '/'.")
    return value


@agentos_cmd.command()
@click.argument("dir_names", nargs=-1, metavar="DIR_NAMES")
@click.option("--name", "-n", metavar="AGENTOS_NAME", default="new_agentos",
              callback=validate_agent_name,
              help="Name of this agentOS. This is also the name of "
                   "this agentOS's MLflow Project and Conda env. "
                   "AGENTOS_NAME may not contain ' ', ':', or '/'.")
def init(dir_names, name):
    """Initialize current (or specified) directory as an AgentOS Agent.

    \b
    Arguments:
        [OPTIONAL] DIR_NAMES zero or more space separated directories to
                             initialize. They will be created if they do
                             not exist.

    Creates an agent main.py file, a conda env, and an MLflow project file
    in all directories specified, or if none are specified, then create
    the files in current directory.
    """
    dirs = [Path(".")]
    if dir_names:
        dirs = [Path(d) for d in dir_names]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
        for file_path, content in INIT_FILES.items():
            f = open(d / file_path, "w")
            now = datetime.now().strftime("%b %d, %Y %H:%M:%S")
            header = f"# This file was auto-generated by `agentos init` on {now}."
            f.write(content.format(name=name,
                                   conda_env=CONDA_ENV_FILE.name,
                                   file_header=header))
            f.flush()

        d = "current working directory" if d == Path(".") else d
        click.echo(f"Finished initializing AgentOS agent '{name}' in {d}.")


def _get_subclass_from_file(filename, parent_class):
    """Return first subclass of `parent_class` found in filename, else None."""
    path = Path(filename)
    assert path.is_file(), f"Make {path} is a valid file."
    assert path.suffix == ".py", "Filename must end in .py"

    spec = importlib.util.spec_from_file_location(path.stem, path.absolute())
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for elt in module.__dict__.values():
        if type(elt) is type and issubclass(elt, parent_class):
            print(f"Found first subclass class {elt}; returning it.")
            return elt


@agentos_cmd.command()
@click.argument("run_args", nargs=-1, metavar="RUN_ARGS")
@click.option("--hz", "-h", metavar="HZ", default=40, type=int,
              help="Frequency to call agent.advance().")
@click.option("--max-iters", "-m", metavar="MAX_STEPS", type=int, default=None,
              help="Stop running agent after this many calls to advance().")
def run(run_args, hz, max_iters):
    """ Run an Agentos Agent (agentos.Agent) with an environment (gym.Env).

    \b
    Arguments:
        RUN_ARGS: 0, 1, or 2 space delimited arguments, parse as follows:

    \b
    If no args are specified, look for default files defining agent:
        - look for file named `MLProject` or `main.py` in the current working
          directory and if found, run this directory as an MLflow project.
              - Try to use MLProject file first, using whatever it defines
                as main entry point, and if that doesn't exist
                then run using MLflow without MLProject passing main.py
                as the entry point.
        - else, look for file named `agent.py` in current working
          directory and, if found, then behave in the same was as if 1
          argument (i.e., `agent.py`) was provided, as described below.
    Else, if 1 arg is specified, interpret it as `agent_filename`:
        - if it is a directory name, assume it is an AgentOS agent dir,
          and behavior is equivalent of `cd`ing into that directory
          and running `agentos run` (without arguments) in it (see above).
        - if it is a file name, the file must contain an agent class and env
          class definition. AgentOS searches that file for the first subclass
          of agentos.Agent, as well as first subclass of gym.Env and calls
          agentos.run_agent() passing in the agent and env classes found.
    Else, if 2 args specified, interpret them as either filenames or py classes.
         - assume the first arg specifies the agent and second specifies
           the Env. The following parsing rules are applied independently
           to each of the two args (e.g., filenames and classes can be mixed):
             - if the arg is a filename:
                  Look for the first instance of the appropriate subclass
                  (either agentos.Agent or gym.env) in the file and use that
                  as the argument to agentos.run_agent.
              - else:
                  Assume the arg is in the form [package.][module.]classname
                  and that it is available in this python environments path.

    """
    def _handle_no_run_args(dirname=None):
        if dirname:
            agent_dir = Path(dirname)
            assert agent_dir.is_dir()
        else:
            agent_dir = Path("./")
        if (agent_dir / MLFLOW_PROJECT_FILE).is_file():
            print(f"Running agent in this dir via MLflow.")
            mlflow.projects.run(str(agent_dir.absolute()))
            return
        elif (agent_dir / AGENT_MAIN_FILE).is_file():
            print(f"Running agent in this dir via MLflow with "
                  f"entry point {AGENT_MAIN_FILE}.")
            mlflow.projects.run(str(agent_dir.absolute()),
                                entry_point=AGENT_MAIN_FILE.name)
        else:
            if not (agent_dir / AGENT_DEF_FILE).is_file():
                raise click.UsageError("No args were passed to run, so one "
                                       f"of {MLFLOW_PROJECT_FILE}, "
                                       f"{AGENT_MAIN_FILE}, "
                                       f"{AGENT_DEF_FILE} must exist.")
            _handle_single_run_arg(agent_dir / AGENT_DEF_FILE)

    def _handle_single_run_arg(filename):
        # The file must contain >= 1 agentos.Agent subclass and >= 1 gym.Env subclass.
        agent_cls = _get_subclass_from_file(filename, agentos.Agent)
        env_cls = _get_subclass_from_file(filename, gym.Env)
        assert agent_cls and env_cls, \
            f" {filename} must contain >= 1 agentos.Agent subclass " \
            f"and >= 1 gym.Env subclass."
        agentos.run_agent(agent_cls, env_cls, hz=hz, max_iters=max_iters)

    if len(run_args) == 0:
        _handle_no_run_args()
    elif len(run_args) == 1:
        if Path(run_args[0]).is_dir():
            _handle_no_run_args(run_args[0])
        if Path(run_args[0]).is_file():
            _handle_single_run_arg(run_args[0])
        else:
            raise click.UsageError("1 argument was passed to run; it must be "
                                   "a filename and it is not. (The file "
                                   "should define your agent class.)")
    elif len(run_args) == 2:
        agent_arg, env_arg = run_args[0], run_args[1]
        if Path(agent_arg).is_file():
            agent_cls = _get_subclass_from_file(agent_arg, agentos.Agent)
            assert agent_cls, f"{agent_arg} must contain a subclass of agentos.Agent"
        else:
            ag_mod_name = ".".join(agent_arg.split(".")[:-1])
            ag_cls_name = agent_arg.split(".")[-1]
            ag_mod = importlib.import_module(ag_mod_name)
            agent_cls = getattr(ag_mod, ag_cls_name)
        if Path(env_arg).is_file():
            env_cls = _get_subclass_from_file(env_arg, gym.Env)
            assert env_cls, f"{env_arg} must contain a subclass of gym.Env"
        else:
            env_mod_name = ".".join(env_arg.split(".")[:-1])
            env_cls_name = env_arg.split(".")[-1]
            env_mod = importlib.import_module(env_mod_name)
            env_cls = getattr(env_mod, env_cls_name)
        agentos.run_agent(agent_cls, env_cls, hz=hz, max_iters=max_iters)
    else:
        raise click.UsageError("run command can take 0, 1, or 2 arguments.")


if __name__ == "__main__":
    agentos_cmd()

