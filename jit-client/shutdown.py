import signal,logging

class GracefulShutdown:
    def __init__(self,logger):
        self.shutdown_signal = False
        self.logger = logger
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        self.logger.info(f'Shutting down on signal {signum}')
        self.shutdown_signal = True