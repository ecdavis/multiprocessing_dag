import logging
import multiprocessing
import random
import time

logger = logging.getLogger(__name__)


class BaseCommand:
    def __init__(self):
        self.parent = None

    def run(self):
        raise NotImplementedError()


class Node:
    def __init__(self, name):
        self.name = name
        self.parent = None
        self.upstreams = set()
        self.downstreams = set()

    def parents(self):
        if self.parent:
            return self.parent.parents() + [self]
        else:
            return [self]

    def path(self):
        return [node.name for node in self.parents()]

    def uri(self):
        return '/'.join(self.path())


class Task(Node):
    def __init__(self, name, commands=None):
        super().__init__(name)

        self.commands = []
        for command in commands or []:
            self.add_command(command)

    def add_command(self, command):
        command.parent = self
        self.commands.append(command)

    def run(self):
        for command in self.commands:
            if not command.run():
                return False
        return True


class Pipeline(Node):
    def __init__(self, name):
        super().__init__(name)

        self.nodes = {}

    def add(self, node, upstreams=None):
        if node.name in self.nodes:
            raise ValueError()  # TODO better exception

        node.parent = self
        self.nodes[node.name] = node

        for upstream in upstreams or []:
            self.add_dependency(upstream, node)

    def add_dependency(self, upstream, downstream):
        upstream.downstreams.add(downstream)
        downstream.upstreams.add(upstream)


class Process(multiprocessing.Process):
    def __init__(self, task, status_queue):
        super().__init__(name=f"task-{task.uri()}")  # TODO don't use uri

        self.task = task
        self.status_queue = status_queue

    def run(self):
        success = True
        try:
            result = self.task.run()
            if not result:
                success = False
        except Exception:  # TODO let KeyboardInterrupt and others bubble up
            success = False
        self.status_queue.put(success)


class Runner:
    def __init__(self, process_limit=4):  # TODO get core count? at least factor this in to a constant
        self.process_limit = process_limit
        self.queued_nodes = []
        self.finished_nodes = set()
        self.running_pipelines = set()
        self.failed_pipelines = set()
        self.running_tasks = {}

    def _dequeue(self):
        for node in self.queued_nodes:
            if not node.upstreams or node.upstreams.issubset(self.finished_nodes):
                self.queued_nodes.remove(node)
                if node.parent in self.failed_pipelines:
                    self.finished_nodes.add(node)
                else:
                    return node
        return None

    def _enqueue_pipeline(self, pipeline):
        for upstream in next_node.upstreams:
            for sub_node in next_node.nodes.values():
                if not sub_node.upstreams:  # TODO shouldn't we add it in all cases?
                    next_node.add_dependency(upstream, sub_node)
        for downstream in next_node.downstreams:
            for sub_node in next_node.nodes.values():
                if not sub_node.downstreams:  # TODO shouldn't we add it in all cases?
                    next_node.add_dependency(sub_node, downstream)
        self.running_pipelines.add(next_node)
        for sub_node in next_node.nodes.values():
            self.queued_nodes.append(sub_node)

    def _start_task(self, task):
        status_queue = multiprocessing.Queue()
        task_process = Process(task, status_queue)
        task_process.start()
        return task_process

    def _finish_tasks(self):
        for running_process in list(self.running_tasks.values()):
            # NOTE tests indicated that is_alive could sometimes return true even when process execution had been
            # NOTE completed, so we also check the status queue even though that's documented as being unreliable
            # NOTE further testing needed here, I think
            if running_process.is_alive() and running_process.status_queue.empty():
                continue
            logger.info("Finishing task '{running_process.task.url()}'.")
            del self.running_tasks[running_process.task]
            self.finished_nodes.add(running_process.task)
            failed = (running_process.exitcode != 0 or not running_process.status_queue.get())
            if failed:
                for parent in running_process.task.parents()[:-1]:
                    self.failed_pipelines.add(parent)

    def _finish_pipelines(self):
        for running_pipeline in list(self.running_pipelines):
            if set(running_pipelines.nodes.values()).issubset(self.finished_nodes):
                logger.info(f"Finishing pipeline '{running_pipeline.uri()}'.")
                # failed = (running_pipeline in self.failed_pipelines)  # TODO
                self.running_pipelines.remove(running_pipeline)
                self.finished_nodes.add(running_pipeline)

    def run(self, pipeline):
        self.queued_nodes.append(pipeline)

        while self.queued_nodes or self.running_tasks:
            if len(self.running_tasks) < self.process_limit:
                next_node = self._dequeue()
                if isinstance(next_node, Pipeline):
                    logger.info(f"Starting pipeline '{next_node.uri()}'.")
                    self._enqueue_pipeline(next_node)
                elif isinstance(next_node, Task):
                    logger.info(f"Starting task '{next_node.uri()}'.")
                    node_process = self._start_task(task)
                    self.running_tasks[next_node] = node_process
                else:
                    pass  # NOTE happens when we dequeue None
            self._finish_tasks()
            self._finish_pipelines()
            time.sleep(0.001)

        self._finish_pipelines()
