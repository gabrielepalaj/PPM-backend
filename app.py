from . import create_app
import threading
from . import monitor

def main():
    print("Starting monitoring thread")
    task_thread = threading.Thread(target=monitor.monitor_websites)
    task_thread.daemon = True
    task_thread.start()

app = create_app()

if __name__ == '__main__':
    main()
    app.run(debug=True)