from flask import Flask, render_template, request, redirect, url_for
from flask_socketio import SocketIO, join_room, leave_room, send, emit
import random
import string
from datetime import datetime

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB
socketio = SocketIO(app)

#This is all we need to track users
users_in_rooms = {}

#Function to generate a random 5-letter room code
def generate_room_code(length=5):
    return ''.join(random.choices(string.ascii_uppercase, k=length))

#Home route
@app.route('/', methods=["GET", "POST"])
def home():
    if request.method == "POST":
        name = request.form.get("name")
        room = request.form.get("room")
        join = request.form.get("join", False)
        create = request.form.get("create", False)

        if not name:  
            return render_template("index.html", error="Name is required.")  

        if join:  
            if not room:  
                return render_template("index.html", error="Room code is required to join.")  
            if room not in users_in_rooms:  
                return render_template("index.html",error="Room does not exist.")  
            if any(user['name'] == name for user in users_in_rooms[room]):  
                return render_template("index.html",error="Username is already available")  
        elif create:  
            room = generate_room_code()  
            while room in users_in_rooms:  # To check room is already available  
                room = generate_room_code()  
            users_in_rooms[room] = []  #initialize room  

        return redirect(url_for("chat", name=name, room=room))  

    return render_template("index.html")

#Chat page route
@app.route('/chat')
def chat():
    name = request.args.get("name")
    room = request.args.get("room")

    if name is None or room is None:  
        return redirect(url_for("home"))  

    return render_template("chat.html", name=name, room=room)

#Message handler
@socketio.on('message')
def handle_message(data):
    name = data['name']
    room = data['room']
    message = data['message']
    timestamp = datetime.now().strftime('%H:%M:%S')
    send({'name': name, 'message': message, 'time': timestamp}, room=room)

#User joins room
@socketio.on('join')
def handle_join(data):
    name = data['name']
    room = data['room']

    join_room(room)  

    if room not in users_in_rooms:  
        users_in_rooms[room] = []  
    
    for user in users_in_rooms[room]:
        if user['name'] == name:
            user['id'] = request.sid
            emit('you_are_admin',{'is_admin' : user['is_admin'],'userId' : request.sid},room = request.sid)
            return 
 
# If first user in room, make them admin  
    is_admin = len(users_in_rooms[room]) == 0  

    users_in_rooms[room].append({  
        'name': name,  
        'id': request.sid,  
        'is_admin': is_admin  
    })  
    # Let the joining user know if they're admin  
    emit('you_are_admin', {'is_admin': is_admin, 'userId': request.sid}, room=request.sid)  

    # Notify room  
    emit('message', {'name': None, 'message': f"{name} has entered the room."}, room=room)

#User leaves room
@socketio.on('leave')
def handle_leave(data):
    name = data['name']
    room = data['room']

    leave_room(room)  

    if room in users_in_rooms:   
        users_in_rooms[room] = [user for user in users_in_rooms[room] if user['id'] != request.sid]  

    emit('message', {'name': None, 'message': f"{name} has left the room."}, room=room)

#Send list of users
@socketio.on('request_users')
def handle_request_users(data):
    room = data['room']
    user_list = users_in_rooms.get(room, [])
    emit('user_list', {'users': user_list})

#file sharing
@socketio.on('file_upload')
def handle_file_upload(data):
    file_name = data['fileName']
    file_type = data['fileType']
    file_data = data['fileData']  # Base64 encoded string

# Broadcast to everyone in the room  
    emit('file_shared', {  
        'name': data['name'],  
        'time': datetime.now().strftime("%H:%M"),  
        'fileName': file_name,  
        'fileType': file_type,  
        'fileData': file_data  
    }, room=data['room'])

#typing indicator
@socketio.on('typing')
def handle_typing(data):
    name = data['name']
    room = data['room']
    emit('typing', {'name': name}, room=room, include_self=False)

#remove user
@socketio.on('remove_user')
def handle_remove_user(data):
    room = data['room']
    user_id = data['userId']

    if room in users_in_rooms:  
        users_in_rooms[room] = [user for user in users_in_rooms[room] if user['id'] != user_id]  
        emit('force_leave', {}, room=user_id)  # disconnect them  
        emit('message', {'name': None, 'message': f"A user has been removed from the room."}, room=room)


#Run the app
if __name__ == '__main__':
    socketio.run(app)

