from src.crossword.app import app, socketio

if __name__ == '__main__':
    # This entry point is a loopback-only development launcher. Production
    # deployments must use a Socket.IO-capable production server.
    socketio.run(
        app,
        debug=False,
        host='127.0.0.1',
        port=5001,
        use_reloader=False,
        allow_unsafe_werkzeug=True,
    )
