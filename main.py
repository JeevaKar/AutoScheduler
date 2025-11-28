from flask import Flask, render_template, redirect, session, request, flash, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_session import Session
import secrets
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from datetime import datetime, timedelta
from helper import mark_event_time, mark_time_blocks, min_to_blocks, round_to_nearest_quarter, round_to_nearest_fifteen
import math
import pytz

pst = pytz.timezone("America/Los_Angeles")

class Base(DeclarativeBase):
  pass

db = SQLAlchemy(model_class=Base)

app = Flask(__name__)

app.config["SECRET_KEY"] = secrets.token_hex(16)
app.config["SESSION_PERMANENT"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///database.db"
app.config["SESSION_TYPE"] = "filesystem"

Session(app=app)

db.init_app(app)

class User(db.Model):
	id: Mapped[int] = mapped_column(primary_key=True)
	username: Mapped[str] = mapped_column(unique=True)
	password: Mapped[str] = mapped_column()
	lastUpdate: Mapped[str] = mapped_column(nullable=True)
	workBlockLength: Mapped[int] = mapped_column(nullable=True)
	breakBlockLength: Mapped[int] = mapped_column(nullable=True)
	monWake: Mapped[int] = mapped_column(nullable=True)
	monBed: Mapped[int] = mapped_column(nullable=True)
	tueWake: Mapped[int] = mapped_column(nullable=True)
	tueBed: Mapped[int] = mapped_column(nullable=True)
	wedWake: Mapped[int] = mapped_column(nullable=True)
	wedBed: Mapped[int] = mapped_column(nullable=True)
	thuWake: Mapped[int] = mapped_column(nullable=True)
	thuBed: Mapped[int] = mapped_column(nullable=True)
	friWake: Mapped[int] = mapped_column(nullable=True)
	friBed: Mapped[int] = mapped_column(nullable=True)
	satWake: Mapped[int] = mapped_column(nullable=True)
	satBed: Mapped[int] = mapped_column(nullable=True)
	sunWake: Mapped[int] = mapped_column(nullable=True)
	sunBed: Mapped[int] = mapped_column(nullable=True)

class Event(db.Model):
	id: Mapped[int] = mapped_column(primary_key=True)
	title: Mapped[str]
	date: Mapped[str]
	starttime: Mapped[int]
	endtime: Mapped[int]
	description: Mapped[str] = mapped_column(nullable=True)
	type: Mapped[int]
	task: Mapped[int] = mapped_column(db.ForeignKey('task.id'), nullable=True)
	user_id: Mapped[int] = mapped_column(db.ForeignKey('user.id'))

class schedule(db.Model):
	id: Mapped[int] = mapped_column(primary_key=True)
	title: Mapped[str] = mapped_column()
	user_id: Mapped[int] = mapped_column(db.ForeignKey('user.id'))
	monStart: Mapped[int] = mapped_column(nullable=True)
	monEnd: Mapped[int] = mapped_column(nullable=True)
	tueStart: Mapped[int] = mapped_column(nullable=True)
	tueEnd: Mapped[int] = mapped_column(nullable=True)
	wedStart: Mapped[int] = mapped_column(nullable=True)
	wedEnd: Mapped[int] = mapped_column(nullable=True)
	thuStart: Mapped[int] = mapped_column(nullable=True)
	thuEnd: Mapped[int] = mapped_column(nullable=True)
	friStart: Mapped[int] = mapped_column(nullable=True)
	friEnd: Mapped[int] = mapped_column(nullable=True)
	satStart: Mapped[int] = mapped_column(nullable=True)
	satEnd: Mapped[int] = mapped_column(nullable=True)
	sunStart: Mapped[int] = mapped_column(nullable=True)
	sunEnd: Mapped[int] = mapped_column(nullable=True)

class task(db.Model):
	id: Mapped[int] = mapped_column(primary_key=True)
	title: Mapped[str] = mapped_column()
	user_id: Mapped[int] = mapped_column(db.ForeignKey('user.id'))
	description: Mapped[str] = mapped_column(nullable=True)
	dueDate: Mapped[str]
	dueTime: Mapped[int]
	completionTime: Mapped[int]
	completed: Mapped[bool] = mapped_column(default=False)

with app.app_context():
	db.create_all()

def generateCalendar(events):
	finalString = ''
	counter = [0, 0, 0, 0, 0, 0, 0]
	for hour in range(0, 24):
		for minute in [0, 15, 30, 45]:
			finalString += '<tr>\n'
			if minute == 0 or minute == 30:
				finalString += f'    <td class="time" id="{hour:02d}:{minute:02d}">{hour:02d}:{minute:02d}</td>\n'
			else:
				finalString += f'    <td class="time" id="{hour:02d}:{minute:02d}"></td>\n'
			for day in range(0, 7):
				if counter[day] > 0:
					finalString += ''
					counter[day] -= 1
					continue
				for event in events:
					if event.weekday_index == day and round_to_nearest_quarter(event.starttime) == f"{hour:02d}:{minute:02d}":
						if event.type == 0:
							finalString += f'<td rowspan="{event.duration}" class = "calEvent calSleep"> {event.title} </td>\n'
						elif event.type == 1:
							finalString += f'<td rowspan="{event.duration}" class = "calEvent calUserEvent"> {event.title} </br><a href="{url_for('editEvent', id=event.id)}"><button>Edit Event</button></a></td>\n'
						elif event.type == 2:
							finalString += f'<td rowspan="{event.duration}" class = "calEvent calTask"> {event.title} </br><a href="{url_for('taskSub', id=event.task, amount=event.duration, eventId = event.id)}"><button>Completed Expected Duration</button></a></td>\n'
						elif event.type == 3:
							finalString += f'<td rowspan="{event.duration}" class = "calEvent calSched"> {event.title} </td>\n'
						elif event.type == 4:
							finalString += f'<td rowspan="{event.duration}" class = "calEvent calTask"> {event.title} </br><a href="{url_for('taskAdd', id=event.task, amount=event.duration, eventId = event.id)}"><button>Add Expected Duration</button></a></td>\n'
						counter[day] = event.duration - 1
						break
				else:
					finalString += '<td></td>\n'
			finalString += '</tr>\n'

	return finalString

def generateBlocks(dayBlocks):
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	stmt = db.select(task).filter_by(user_id=user.id, completed=False).order_by(task.dueDate, task.dueTime)
	tasks = db.session.execute(stmt).scalars().all()
	if user.workBlockLength:
		workBlock = min_to_blocks(user.workBlockLength)
	else:
		workBlock = 96

	for t in tasks:
		db.session.expunge(t)

	i = 0
	breakFlag = False
	while i < len(tasks):
		taskObj = tasks[i]
		req = math.ceil(int(taskObj.completionTime) / 15)
		starttime = None
		endtime = None
		length = 0
		for j in range(len(dayBlocks)):
			if length >= workBlock:
				breakFlag = True
			if dayBlocks[j] == 0 and starttime is None and req > 0:
				length += 1
				starttime = j
				req -= 1
			elif dayBlocks[j] == 0 and starttime is not None:
				length += 1
				if breakFlag and req > 0:
					req -= 1
					endtime = j
					tasks[i].completionTime = (req + 1) * 15
					i -= 1
					break
				if req > 0:
					req -= 1
				elif req == 0:
					endtime = j
					break
			elif dayBlocks[j] == 1 and starttime is not None:
				endtime = j
				tasks[i].completionTime = (req + 1) * 15
				i -= 1
				break
		if starttime is not None and endtime is not None:
			start_hour = starttime // 4
			start_minute = (starttime % 4) * 15
			end_hour = endtime // 4
			end_minute = (endtime % 4) * 15
			start_str = f"{start_hour:02}:{start_minute:02}"
			end_str = f"{end_hour:02}:{end_minute:02}"
			scheduledEvent = Event(
				title = taskObj.title,
				date = datetime.now(pst).date().strftime('%Y-%m-%d'),
				starttime = start_str,
				endtime = end_str,
				description = "Task Scheduled",
				type = 2,
				task = taskObj.id,
				user_id = user.id
			)
			db.session.add(scheduledEvent)
			db.session.commit()
			dayBlocks = mark_event_time(dayBlocks, scheduledEvent.starttime, scheduledEvent.endtime)
		if breakFlag:
			start_hour = endtime // 4
			start_minute = (endtime % 4) * 15
			break_length = min_to_blocks(user.breakBlockLength)
			end_hour = (endtime + break_length) // 4
			end_minute = ((endtime + break_length) % 4) * 15
			scheduledEvent = Event(
				title = "Break",
				date = datetime.now(pst).date().strftime('%Y-%m-%d'),
				starttime = f"{start_hour:02}:{start_minute:02}",
				endtime = f"{end_hour:02}:{end_minute:02}",
				description = "Break",
				type = 0,
				user_id = user.id
			)
			db.session.add(scheduledEvent)
			db.session.commit()
			dayBlocks = mark_event_time(dayBlocks, scheduledEvent.starttime, scheduledEvent.endtime)
			breakFlag = False
		i += 1
	del tasks

def update():
	dayBlocks = [0] * (24 * 4)  # 96 blocks of 15 minutes in a day
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	stmt = db.select(schedule).filter_by(user_id=user.id)
	schedules = db.session.execute(stmt).scalars().all()
	today = datetime.now(pst).date()
	if user.monWake:
		match today.strftime('%a'):
			case "Mon":
				sleepMorning = Event(
					title = "Sleep",
					date = today.strftime('%Y-%m-%d'),
					starttime = "00:00",
					endtime = user.monWake,
					description = "Sleep",
					type = 0,
					user_id = user.id
				)
				sleepNight = Event(
					title = "Sleep",
					date = today.strftime('%Y-%m-%d'),
					starttime = user.monBed,
					endtime = "23:59",
					description = "Sleep",
					type = 0,
					user_id = user.id
				)
			case "Tue":
				sleepMorning = Event(
					title = "Sleep",
					date = today.strftime('%Y-%m-%d'),
					starttime = "00:00",
					endtime = user.tueWake,
					description = "Sleep",
					type = 0,
					user_id = user.id
				)
				sleepNight = Event(
					title = "Sleep",
					date = today.strftime('%Y-%m-%d'),
					starttime = user.tueBed,
					endtime = "23:59",
					description = "Sleep",
					type = 0,
					user_id = user.id
				)
			case "Wed":
				sleepMorning = Event(
					title = "Sleep",
					date = today.strftime('%Y-%m-%d'),
					starttime = "00:00",
					endtime = user.wedWake,
					description = "Sleep",
					type = 0,
					user_id = user.id
				)
				sleepNight = Event(
					title = "Sleep",
					date = today.strftime('%Y-%m-%d'),
					starttime = user.wedBed,
					endtime = "23:59",
					description = "Sleep",
					type = 0,
					user_id = user.id
				)
			case "Thu":
				sleepMorning = Event(
					title = "Sleep",
					date = today.strftime('%Y-%m-%d'),
					starttime = "00:00",
					endtime = user.thuWake,
					description = "Sleep",
					type = 0,
					user_id = user.id
				)
				sleepNight = Event(
					title = "Sleep",
					date = today.strftime('%Y-%m-%d'),
					starttime = user.thuBed,
					endtime = "23:59",
					description = "Sleep",
					type = 0,
					user_id = user.id
				)
			case "Fri":
				sleepMorning = Event(
					title = "Sleep",
					date = today.strftime('%Y-%m-%d'),
					starttime = "00:00",
					endtime = user.friWake,
					description = "Sleep",
					type = 0,
					user_id = user.id
				)
				sleepNight = Event(
					title = "Sleep",
					date = today.strftime('%Y-%m-%d'),
					starttime = user.friBed,
					endtime = "23:59",
					description = "Sleep",
					type = 0,
					user_id = user.id
				)
			case "Sat":
				sleepMorning = Event(
					title = "Sleep",
					date = today.strftime('%Y-%m-%d'),
					starttime = "00:00",
					endtime = user.SatWake,
					description = "Sleep",
					type = 0,
					user_id = user.id
				)
				sleepNight = Event(
					title = "Sleep",
					date = today.strftime('%Y-%m-%d'),
					starttime = user.satBed,
					endtime = "23:59",
					description = "Sleep",
					type = 0,
					user_id = user.id
				)
			case "Sun":
				sleepMorning = Event(
					title = "Sleep",
					date = today.strftime('%Y-%m-%d'),
					starttime = "00:00",
					endtime = user.sunWake,
					description = "Sleep",
					type = 0,
					user_id = user.id
				)
				sleepNight = Event(
					title = "Sleep",
					date = today.strftime('%Y-%m-%d'),
					starttime = user.sunBed,
					endtime = "23:59",
					description = "Sleep",
					type = 0,
					user_id = user.id
				)
		
		db.session.add(sleepMorning)
		db.session.add(sleepNight)
		dayBlocks = mark_event_time(dayBlocks, sleepMorning.starttime, sleepMorning.endtime)
		dayBlocks = mark_event_time(dayBlocks, sleepNight.starttime, sleepNight.endtime)
	
	for scheduleObj in schedules:
		match today.strftime('%a'):
			case "Mon":
				if scheduleObj.monStart and scheduleObj.monEnd:
					scheduledEvent = Event(
						title = scheduleObj.title,
						date = today.strftime('%Y-%m-%d'),
						starttime = scheduleObj.monStart,
						endtime = scheduleObj.monEnd,
						description = "Scheduled Event",
						type = 3,
						user_id = user.id
					)
					db.session.add(scheduledEvent)
					dayBlocks = mark_event_time(dayBlocks,  scheduledEvent.starttime, scheduledEvent.endtime)
			case "Tue":
				if scheduleObj.tueStart and scheduleObj.tueEnd:
					scheduledEvent = Event(
						title = scheduleObj.title,
						date = today.strftime('%Y-%m-%d'),
						starttime = scheduleObj.tueStart,
						endtime = scheduleObj.tueEnd,
						description = "Scheduled Event",
						type = 3,
						user_id = user.id
					)
					db.session.add(scheduledEvent)
					dayBlocks = mark_event_time(dayBlocks,  scheduledEvent.starttime, scheduledEvent.endtime)
			case "Wed":
				if scheduleObj.wedStart and scheduleObj.wedEnd:
					scheduledEvent = Event(
						title = scheduleObj.title,
						date = today.strftime('%Y-%m-%d'),
						starttime = scheduleObj.wedStart,
						endtime = scheduleObj.wedEnd,
						description = "Scheduled Event",
						type = 3,
						user_id = user.id
					)
					db.session.add(scheduledEvent)
					dayBlocks = mark_event_time(dayBlocks,  scheduledEvent.starttime, scheduledEvent.endtime)
			case "Thu":
				if scheduleObj.thuStart and scheduleObj.thuEnd:
					scheduledEvent = Event(
						title = scheduleObj.title,
						date = today.strftime('%Y-%m-%d'),
						starttime = scheduleObj.thuStart,
						endtime = scheduleObj.thuEnd,
						description = "Scheduled Event",
						type = 3,
						user_id = user.id
					)
					db.session.add(scheduledEvent)
					dayBlocks = mark_event_time(dayBlocks,  scheduledEvent.starttime, scheduledEvent.endtime)
			case "Fri":
				if scheduleObj.friStart and scheduleObj.friEnd:
					scheduledEvent = Event(
						title = scheduleObj.title,
						date = today.strftime('%Y-%m-%d'),
						starttime = scheduleObj.friStart,
						endtime = scheduleObj.friEnd,
						description = "Scheduled Event",
						type = 3,
						user_id = user.id
					)
					db.session.add(scheduledEvent)
					dayBlocks = mark_event_time(dayBlocks,  scheduledEvent.starttime, scheduledEvent.endtime)
			case "Sat":
				if scheduleObj.satStart and scheduleObj.satEnd:
					scheduledEvent = Event(
						title = scheduleObj.title,
						date = today.strftime('%Y-%m-%d'),
						starttime = scheduleObj.satStart,
						endtime = scheduleObj.satEnd,
						description = "Scheduled Event",
						type = 3,
						user_id = user.id
					)
					db.session.add(scheduledEvent)
					dayBlocks = mark_event_time(dayBlocks,  scheduledEvent.starttime, scheduledEvent.endtime)
			case "Sun":
				if scheduleObj.sunStart and scheduleObj.sunEnd:
					scheduledEvent = Event(
						title = scheduleObj.title,
						date = today.strftime('%Y-%m-%d'),
						starttime = scheduleObj.sunStart,
						endtime = scheduleObj.sunEnd,
						description = "Scheduled Event",
						type = 3,
						user_id = user.id
					)
					db.session.add(scheduledEvent)
					dayBlocks = mark_event_time(dayBlocks,  scheduledEvent.starttime, scheduledEvent.endtime)
	
	stmt = db.select(Event).filter_by(user_id=user.id, date=today.strftime('%Y-%m-%d'))
	events = db.session.execute(stmt).scalars().all()
	for event in events:
		dayBlocks = mark_event_time(dayBlocks, event.starttime, event.endtime)
	user.lastUpdate = str(datetime.now(pst).strftime('%Y-%m-%d'))
	dayBlocks = mark_time_blocks(dayBlocks)
	generateBlocks(dayBlocks)
	db.session.commit()

def clearEvents():
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	stmt = db.select(Event).filter_by(user_id = user.id, date = datetime.now(pst).strftime('%Y-%m-%d')).filter(Event.type.in_([0, 2, 3]))
	events = db.session.execute(stmt).scalars().all()
	for event in events:
		db.session.delete(event)
	db.session.commit()

def get_start_of_week(d):
	return d - timedelta(days=d.weekday())

@app.route('/')
@app.route('/calendar')
def home():
	if not session.get("username"):
		return redirect('/login')
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	if user.lastUpdate != str(datetime.now(pst).strftime('%Y-%m-%d')):
		update()
	stmt = db.select(Event).filter_by(user_id=user.id)
	events = db.session.execute(stmt).scalars().all()

	today = datetime.now(pst).date()
	week_start = get_start_of_week(today)
	week_end = week_start + timedelta(days=6)

	filtered_events = []

	for event in events:
		# Convert string dates if necessary
		if isinstance(event.date, str):
			event_date = datetime.strptime(event.date, "%Y-%m-%d").date()
		else:
			event_date = event.date

		# Keep only events within the week
		if week_start <= event_date <= week_end:
			# Convert to weekday number 0–6
			event.weekday_index = event_date.weekday()  # Monday=0, Sunday=6
			filtered_events.append(event)

	events = filtered_events
	filtered_events = []
	
	for event in events:
		# convert "HH:MM" → datetime.time
		start = datetime.strptime(round_to_nearest_quarter(event.starttime), "%H:%M")
		if event.endtime == "23:59":
			end = datetime.strptime(event.endtime, "%H:%M")
		else:
			end = datetime.strptime(round_to_nearest_quarter(event.endtime), "%H:%M")

		# compute duration in minutes
		duration_minutes = int((end - start).total_seconds() / 60)

		# convert to 15-minute blocks
		event.duration = math.ceil(duration_minutes / 15)

		filtered_events.append(event)
	
	table = generateCalendar(filtered_events)
	time = round_to_nearest_quarter(datetime.now(pst).strftime('%H:%M'))
	return render_template('index.jinja', table=table, time=time)

@app.route('/login', methods=["GET", "POST"])
def login():
	if request.method == "POST":
		user = db.one_or_404(db.select(User).filter_by(username = request.form["username"]))
		if user.password == request.form["password"]:
			session["username"] = user.username
			flash(f"{user.username} is now logged in!")
			return redirect(url_for('home'))
	return render_template('login.jinja')

@app.route('/signup', methods=["GET", "POST"])
def signup():
	if request.method == "POST":
		if request.form.get("password") == request.form.get("cpassword"):
			user = User(
				username = request.form["username"],
				password = request.form["password"]
			)
			db.session.add(user)
			db.session.commit()
			flash("Your account was created!")
			return redirect(url_for('login'))
	return render_template('signup.jinja')

@app.route('/edit_sleep_schedule', methods=["GET", "POST"])
def edit_sleep_schedule():
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	if request.method == "POST":
		clearEvents()
		user.lastUpdate = None
		user.monWake = request.form.get("monWake")
		user.tueWake = request.form.get("tueWake")
		user.wedWake = request.form.get("wedWake")
		user.thuWake = request.form.get("thuWake")
		user.friWake = request.form.get("friWake")
		user.satWake = request.form.get("satWake")
		user.sunWake = request.form.get("sunWake")

		user.monBed = request.form.get("monBed")
		user.tueBed = request.form.get("tueBed")
		user.wedBed = request.form.get("wedBed")
		user.thuBed = request.form.get("thuBed")
		user.friBed = request.form.get("friBed")
		user.satBed = request.form.get("satBed")
		user.sunBed = request.form.get("sunBed")
		db.session.commit()
		flash("Sleep schedule updated!")
		return redirect(url_for('home'))
	return render_template('edit_sleep_schedule.jinja', user = user)

@app.route('/view_schedules')
def viewSchedules():
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	stmt = db.select(schedule).filter_by(user_id=user.id)
	schedules = db.session.execute(stmt).scalars().all()
	return render_template('scheduleView.jinja', schedules=schedules)

@app.route('/edit_schedule/<int:id>', methods=["GET", "POST"])
def editSchedule(id):
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	scheduleObj = db.one_or_404(db.select(schedule).filter_by(id=id, user_id=user.id))
	if request.method == "POST":
		scheduleObj.title = request.form.get("title")
		scheduleObj.monStart = request.form.get("monStart")
		scheduleObj.monEnd = request.form.get("monEnd")
		scheduleObj.tueStart = request.form.get("tueStart")
		scheduleObj.tueEnd = request.form.get("tueEnd")
		scheduleObj.wedStart = request.form.get("wedStart")
		scheduleObj.wedEnd = request.form.get("wedEnd")
		scheduleObj.thuStart = request.form.get("thuStart")
		scheduleObj.thuEnd = request.form.get("thuEnd")
		scheduleObj.friStart = request.form.get("friStart")
		scheduleObj.friEnd = request.form.get("friEnd")
		scheduleObj.satStart = request.form.get("satStart")
		scheduleObj.satEnd = request.form.get("satEnd")
		scheduleObj.sunStart = request.form.get("sunStart")
		scheduleObj.sunEnd = request.form.get("sunEnd")
		user.lastUpdate = None
		clearEvents()
		db.session.commit()
		flash("Schedule updated!")
		return redirect(url_for('viewSchedules'))
	return render_template('editSchedule.jinja', schedule = scheduleObj)

@app.route('/add_schedule', methods=["GET", "POST"])
def addSchedule():
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	if request.method == "POST":
		scheduleObj = schedule(
			title = request.form.get("title"),
			user_id = user.id,
			monStart = request.form.get("monStart"),
			monEnd = request.form.get("monEnd"),
			tueStart = request.form.get("tueStart"),
			tueEnd = request.form.get("tueEnd"),
			wedStart = request.form.get("wedStart"),
			wedEnd = request.form.get("wedEnd"),
			thuStart = request.form.get("thuStart"),
			thuEnd = request.form.get("thuEnd"),
			friStart = request.form.get("friStart"),
			friEnd = request.form.get("friEnd"),
			satStart = request.form.get("satStart"),
			satEnd = request.form.get("satEnd"),
			sunStart = request.form.get("sunStart"),
			sunEnd = request.form.get("sunEnd")
		)
		db.session.add(scheduleObj)
		user.lastUpdate = None
		clearEvents()
		db.session.commit()
		flash("Schedule added!")
		return redirect(url_for('viewSchedules'))
	return render_template('addSchedule.jinja')

@app.route('/delete_schedule/<int:id>')
def deleteSchedule(id):
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	scheduleObj = db.one_or_404(db.select(schedule).filter_by(id=id, user_id=user.id))
	db.session.delete(scheduleObj)
	user.lastUpdate = None
	clearEvents()
	db.session.commit()
	flash("Schedule deleted!")
	return redirect(url_for('viewSchedules'))

@app.route('/add_event', methods=["GET", "POST"])
def addEvent():
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	if request.method == "POST":
		event = Event(
			title = request.form.get("title"),
			date = request.form.get("date"),
			starttime = request.form.get("starttime"),
			endtime = request.form.get("endtime"),
			type = 1,
			user_id = user.id
		)
		db.session.add(event)
		user.lastUpdate = None
		clearEvents()
		db.session.commit()
		flash("Event added!")
		return redirect(url_for('home'))
	return render_template('addEvent.jinja')

@app.route('/add_task', methods=["GET", "POST"])
def addTask():
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	if request.method == "POST":
		taskObj = task(
			title = request.form.get("title"),
			dueDate = request.form.get("dueDate"),
			dueTime = request.form.get("dueTime"),
			completionTime = request.form.get("completionTime"),
			user_id = user.id
		)
		db.session.add(taskObj)
		user.lastUpdate = None
		clearEvents()
		db.session.commit()
		flash("Task added!")
		return redirect(url_for('home'))
	return render_template('addTask.jinja')

@app.route('/view_tasks')
def viewTasks():
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	stmt = db.select(task).filter_by(user_id=user.id, completed=False).order_by(task.dueDate, task.dueTime, task.completionTime)
	tasks = db.session.execute(stmt).scalars().all()
	return render_template('taskView.jinja', tasks=tasks)

@app.route('/edit_task/<int:id>', methods=["GET", "POST"])
def editTask(id):
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	taskObj = db.one_or_404(db.select(task).filter_by(id=id, user_id=user.id))
	if request.method == "POST":
		taskObj.title = request.form.get("title")
		taskObj.dueDate = request.form.get("dueDate")
		taskObj.dueTime = request.form.get("dueTime")
		taskObj.completionTime = request.form.get("completionTime")
		user.lastUpdate = None
		clearEvents()
		db.session.commit()
		flash("Task updated!")
		return redirect(url_for('viewTasks'))
	return render_template('editTask.jinja', task = taskObj)

@app.route('/complete_task/<int:id>')
def completeTask(id):
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	taskObj = db.one_or_404(db.select(task).filter_by(id=id, user_id=user.id))
	taskObj.completionTime = 0
	taskObj.completed = True
	user.lastUpdate = None
	clearEvents()
	db.session.commit()
	flash("Task completed!")
	return redirect(url_for('viewTasks'))

@app.route('/edit_event/<int:id>', methods=["GET", "POST"])
def editEvent(id):
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	eventObj = db.one_or_404(db.select(Event).filter_by(id=id, user_id=user.id))
	if request.method == "POST":
		eventObj.title = request.form.get("title")
		eventObj.date = request.form.get("date")
		eventObj.starttime = request.form.get("starttime")
		eventObj.endtime = request.form.get("endtime")
		user.lastUpdate = None
		clearEvents()
		db.session.commit()
		flash("Event updated!")
		return redirect(url_for('home'))
	return render_template('editEvent.jinja', event = eventObj)

@app.route('/delete_event/<int:id>')
def deleteEvent(id):
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	eventObj = db.one_or_404(db.select(Event).filter_by(id=id, user_id=user.id))
	db.session.delete(eventObj)
	db.session.commit()
	flash("Event deleted!")
	return redirect(url_for('home'))

@app.route('/update')
def manualUpdate():
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	clearEvents()
	user.lastUpdate = None
	db.session.commit()
	return redirect(url_for('home'))

@app.route('/logout')
def logout():
	session.clear()
	return redirect(url_for('login'))

@app.route('/task_sub/<int:id>/<int:amount>/<int:eventId>')
def taskSub(id, amount, eventId):
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	taskObj = db.one_or_404(db.select(task).filter_by(id=id, user_id=user.id))
	taskObj.completionTime -= amount * 15
	if taskObj.completionTime < 0:
		taskObj.completionTime = 0
	eventObj = db.one_or_404(db.select(Event).filter_by(id=eventId, user_id=user.id))
	eventObj.type = 4
	user.lastUpdate = None
	clearEvents()
	db.session.commit()
	flash("Task time updated!")
	return redirect(url_for('home'))

@app.route('/settings', methods=["GET", "POST"])
def settings():
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	if request.method == "POST":
		user.workBlockLength = round_to_nearest_fifteen(int(request.form.get("worktime")))
		user.breakBlockLength = round_to_nearest_fifteen(int(request.form.get("breaktime")))
		user.lastUpdate = None
		clearEvents()
		db.session.commit()
		flash("Settings updated!")
		return redirect(url_for('home'))
	return render_template('settings.jinja', worktime=user.workBlockLength, breaktime=user.breakBlockLength)

@app.route('/task_add/<int:id>/<int:amount>/<int:eventId>')
def taskAdd(id, amount, eventId):
	user = db.one_or_404(db.select(User).filter_by(username = session["username"]))
	taskObj = db.one_or_404(db.select(task).filter_by(id=id, user_id=user.id))
	taskObj.completionTime += amount * 15
	if taskObj.completionTime < 0:
		taskObj.completionTime = 0
	eventObj = db.one_or_404(db.select(Event).filter_by(id=eventId, user_id=user.id))
	db.session.delete(eventObj)
	user.lastUpdate = None
	clearEvents()
	db.session.commit()
	flash("Task time updated!")
	return redirect(url_for('home'))

if __name__ == '__main__':
	app.run(host='0.0.0.0', port=80, debug=True)