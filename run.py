from scholarship_graph.app import app

if __name__ == "__main__":
    print("Running Scholarship Graph Application in Development Mode")
    app.run(host='0.0.0.0', port=7225, debug=True)
