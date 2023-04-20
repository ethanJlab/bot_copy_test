from flask import Flask, request, Response
app = Flask(__name__)
@app.route('/my_webhook', methods=['POST'])
def return_response():
    print(request.json)
    return Response(status=200)
if __name__ == '__main__': app.run()

