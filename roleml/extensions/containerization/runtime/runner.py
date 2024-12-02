import logging
import signal
import threading
import time
from typing import cast

from flask import Flask, request, jsonify

from roleml.core.actor.base import BaseActor
from roleml.extensions.containerization.builders.actor import RoleRuntimeBuilder
from roleml.extensions.containerization.builders.spec import ActorBootstrapSpec
from roleml.extensions.containerization.runtime.impl import RoleRuntime
from roleml.scripts.runner.single import run_actor_gracefully


class RemoteRunner:

    def __init__(self) -> None:
        self._spec: ActorBootstrapSpec | None = None
        self._actor: BaseActor | None = None
        self._instance_name: str = ''
        
        self._profiling: bool = False
        self._save_path: str = '.'
        self._tracer_entries: int = 1000000
        
        self._start_event = threading.Event()
        self._actor_started_event = threading.Event()
        self._actor_start_exception: Exception | None = None
        
        self._stopped_event = threading.Event()

    def _on_setup(self):
        if self._actor is not None:
            return jsonify({"error": "Actor already setup"}), 400
        
        data = request.get_json()
        if data is None:
            return jsonify({"error": "Invalid JSON"}), 400

        self._instance_name = data['instance_name']
        spec = data['config']
        print(f"Setting up actor with spec: {spec}")
        builder = RoleRuntimeBuilder()
        builder.load_config(spec)
        self._actor = builder.build()
        return jsonify({"message": "Setup successful"}), 200

    def _on_run(self):
        self._start_event.set()
        self._actor_started_event.wait()
        if self._actor_start_exception is not None:
            return jsonify({"error": str(self._actor_start_exception)}), 500
        return jsonify({"message": "Actor started"}), 200
    
    def _on_run_with_profiling(self):
        data = request.get_json()
        self._save_path = data.get('save_path', self._save_path)
        self._tracer_entries = data.get('tracer_entries', self._tracer_entries)
        self._profiling = True
        return self._on_run()
    
    def _on_stop(self):
        data = request.get_json(silent=True)
        timeout = data.get('timeout', None) if data is not None else None
        signal.raise_signal(signal.SIGINT)
        if not self._stopped_event.wait(timeout):
            def delayed_kill():
                signal.raise_signal(signal.SIGKILL)
            kill_thread = threading.Timer(1.0, delayed_kill)
            kill_thread.start()
            return jsonify({"error": "Timeout waiting for actor to stop. Forced kill"}), 500
        return jsonify({"message": "Actor stopped"}), 200

    def _serve(self, port: int):
        app = Flask(__name__)
        app.add_url_rule("/setup", view_func=self._on_setup, methods=["POST"])
        app.add_url_rule("/run", view_func=self._on_run, methods=["POST"])
        app.add_url_rule("/run_with_profiling", view_func=self._on_run_with_profiling, methods=["POST"])
        app.add_url_rule("/stop", view_func=self._on_stop, methods=["POST"])

        def run_app():
            app.run(host="0.0.0.0", port=port)

        # serve in a separate thread
        thread = threading.Thread(target=run_app)
        thread.daemon = True
        thread.start()

    def run(self, port: int):
        self._serve(port) # TODO emit event to controller to indicate that the server is running
        # `run_actor_gracefully` has to be called in the main thread
        self._start_event.wait()
        cast(RoleRuntime, self._actor).add_actor_started_callback(
            lambda: self._actor_started_event.set()
        )
        if not self._profiling:
            self._run_actor()
        else:
            self._run_actor_with_profiling()

    def _run_actor(self):
        try:
            assert self._actor is not None, "Actor not setup"
            run_actor_gracefully(self._actor)
        except Exception as e:
            if not self._actor_started_event.is_set():
                self._actor_start_exception = e
                logging.exception("Error starting actor")
                self._actor_started_event.set()
            else:
                self._stopped_event.set()
                time.sleep(2)
                raise

    def _run_actor_with_profiling(self):
        from pathlib import Path
        try:
            from viztracer import VizTracer     # type: ignore
        except ModuleNotFoundError as e:
            e.msg = 'Failed to import viztracer, which is required for profiling. Please install it in your environment.'
            raise e

        assert self._actor is not None
        name = f"{self._actor.profile.name}_{self._instance_name}"
        save_path = (Path(self._save_path) / f'profiler-{name}.json').absolute().as_posix()
        # save_path.parent.mkdir(parents=True, exist_ok=True)

        with VizTracer(output_file=save_path, tracer_entries=self._tracer_entries):
            logging.info(f"Profiling actor {name} with save path {save_path}")
            self._run_actor()
