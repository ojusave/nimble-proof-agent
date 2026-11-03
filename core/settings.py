"""Composition settings; provider modules never read environment variables."""
import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    api_key: str = ''
    api_base: str = 'https://sdk.nimbleway.com/v2'
    data_dir: Path = ROOT / 'data'
    max_rounds: int = 2
    candidates_per_round: int = 12
    linked_candidates: int = 12
    request_timeout: int = 90
    agent_timeout: int = 1200
    agent_effort: str = 'high'
    llama_api_key: str = ''
    llama_api_base: str = 'https://api.cloud.llamaindex.ai'
    llama_parse_version: str = '2026-09-29'
    llama_parse_timeout: int = 180

    @classmethod
    def load(cls):
        # Only this composition layer reads .env. Never return its contents to the UI.
        env = {}
        path = ROOT / '.env'
        if path.exists():
            for line in path.read_text().splitlines():
                key, sep, value = line.partition('=')
                if sep and not key.strip().startswith('#'):
                    env[key.strip()] = value.strip().strip('\"\'')
        return cls(api_key=os.environ.get('NIMBLE_API_KEY', env.get('NIMBLE_API_KEY', '')),
                   llama_api_key=os.environ.get('LLAMA_CLOUD_API_KEY', env.get('LLAMA_CLOUD_API_KEY', '')),
                   data_dir=Path(os.environ.get('PROOF_DATA_DIR', str(ROOT/'data'))))
