"""Local configuration safeguards; no Docker, database, or model calls."""
import base64
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from dev_backend import compose, initialize, load_config, seed
from acceptance import EnvironmentFailure


class DevBackendConfigTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env_file = Path(self.temp.name) / '.env'
        initialize(self.env_file)

    def change(self, key, value):
        lines = self.env_file.read_text().splitlines()
        self.env_file.write_text('\n'.join(
            key + '=' + value if line.startswith(key + '=') else line
            for line in lines) + '\n')

    def test_generated_credentials_are_private_consistent_and_stable(self):
        original = self.env_file.read_bytes()
        config = load_config(self.env_file)
        self.assertEqual(32, len(base64.b64decode(config['JWT_SECRET'], validate=True)))
        self.assertIn(':' + config['POSTGRES_PASSWORD'] + '@', config['DATABASE_URL'])
        self.assertEqual(0o600, self.env_file.stat().st_mode & 0o777)
        self.assertFalse(initialize(self.env_file))
        self.assertEqual(original, self.env_file.read_bytes())

    def test_refuses_remote_or_mismatched_database_before_starting_services(self):
        for url in ('postgresql://user:password@remote.example/demo_test',
                    'postgresql://user:password@127.0.0.1:55459/wrong_test'):
            with self.subTest(url=url):
                self.change('DATABASE_URL', url)
                with self.assertRaises(ValueError):
                    load_config(self.env_file)

    def test_scheduler_cannot_be_enabled_by_local_launcher(self):
        self.change('JOB_SCHEDULER_ENABLED', 'true')
        with self.assertRaises(ValueError):
            load_config(self.env_file)

    def test_ambient_compose_project_cannot_change_the_managed_database(self):
        config = load_config(self.env_file)
        with patch.dict('os.environ', {'COMPOSE_PROJECT_NAME': 'unrelated-project'}):
            with patch('dev_backend.subprocess.run') as run:
                run.return_value.returncode = 0
                compose(['stop', 'db'], config)
        command = run.call_args.args[0]
        self.assertEqual('daynomy-local', command[command.index('--project-name') + 1])

    def test_synthetic_seed_cannot_be_added_after_real_public_import(self):
        with patch('dev_backend.Database') as database, patch('dev_backend.subprocess.run') as run:
            database.return_value.query.return_value = True
            with self.assertRaises(EnvironmentFailure):
                seed(load_config(self.env_file))
            run.assert_not_called()

    def test_env_is_data_and_never_executes_shell_syntax(self):
        marker = Path(self.temp.name) / 'must-not-exist'
        with self.env_file.open('a') as stream:
            stream.write(f'GOOGLE_CLIENT_SECRET=$(touch {marker})\n')
        config = load_config(self.env_file)
        self.assertEqual(f'$(touch {marker})', config['GOOGLE_CLIENT_SECRET'])
        self.assertFalse(marker.exists())

    def test_duplicate_keys_and_missing_settings_fail_without_leaking_values(self):
        secret = load_config(self.env_file)['POSTGRES_PASSWORD']
        with self.env_file.open('a') as stream:
            stream.write('PORT=18110\n')
        with self.assertRaises(ValueError) as failure:
            load_config(self.env_file)
        self.assertNotIn(secret, str(failure.exception))
        self.env_file.write_text('PORT=18109\n')
        with self.assertRaises(ValueError):
            load_config(self.env_file)


if __name__ == '__main__':
    unittest.main()
