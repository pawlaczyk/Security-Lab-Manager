import datetime
from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from django.contrib.auth.forms import UserCreationForm
from django.http import HttpResponseRedirect
from django.views.generic.edit import CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.views import generic
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required

from slmApp.models import Classes, Exercises, Submissions, Settings, CustomUser
from slmApp.forms import LoginForm,SignUpForm,SubmitAnswer

from slmApp.exercises import command,generate_hash
from slmApp.site_stats import update_settings
from slmApp.email import send_mail

# The main login page
def LoginView(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
    form = LoginForm()
    return render(request, 'login.html', {'form': form})
# Decides if should go to instructor or student page
def RedirectLogin(request):
    if request.user.is_superuser == True:
        return HttpResponseRedirect(reverse('instructor'))
    else:
        return HttpResponseRedirect(reverse('student'))

# Signup forms for users and admins
def SignupView(request):
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            login(request, user)
            return redirect('student')
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})
def SignupAdminView(request):
    if request.method == 'POST' and request.user.is_superuser == True:
        form = SignUpForm(request.POST)
        if form.is_valid():
            form.save()
            username = form.cleaned_data.get('username')
            raw_password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=raw_password)
            user.is_superuser = True
            user.save()
            login(request, user)
            return redirect('instructor')
    else:
        form = SignUpForm()
    return render(request, 'signup.html', {'form': form})

# Correct Classes show up based on who you are
@login_required
def StudentView(request):
    form = SubmitAnswer()
    classes = Classes.objects.filter(students=request.user)
    settings = Settings.objects.get(pk=1)
    try: 
        submitted_exercises = Submissions.objects.filter(student=request.user).values_list('exercises',flat=True)
    except Submissions.DoesNotExist:
        submitted = None
    return render(request, 'student.html', {'classes': classes, 'form': form, 'submitted_exercises':submitted_exercises, 'settings':settings})
@login_required
def InstructorView(request):
    if request.user.is_superuser == True:
        classes = Classes.objects.filter(instructor=request.user)
        setting = Settings.objects.get(pk=1)
        return render(request, 'admin.html', {'classes': classes, 'setting':setting})

# submitting answers to the exercises
@login_required
def SubmitExerciseView(request, Cpk, Epk):
    if request.method == 'POST':
        form = SubmitAnswer(request.POST)
        if form.is_valid():
            user_submission = form.cleaned_data.get("submitted")
            exercise = Exercises.objects.get(pk=Epk)
            class_inst = Classes.objects.get(pk=Cpk)
            submission, created = Submissions.objects.get_or_create(student=request.user,exercises=exercise,classes=class_inst)
            submission.submitted = user_submission
            submission.save()
    else:
        form = SubmitAnswer()
    return redirect('student')

@login_required
def SubmissionsView(request, Cpk, Epk):
    if request.method == 'POST' and request.user.is_superuser == True:
        submissions = Submissions.objects.filter(classes=Cpk).filter(exercises=Epk)
        return render(request, 'details_submissions.html', {'submissions': submissions})
def getGrades(Cpk):
    classes = Classes.objects.get(pk=Cpk)
    students = classes.students.all()
    exercises = classes.exercises.all()
    answer = ''

    grades = [["Exercise",],]
    for student in students:
        grades[0].append(student.username)
    # fill out list of zeros for initial percentages
    columns = len(students)
    percentages = []
    for i in range(0,columns):
        percentages.append([0,0])

    # Exercise Name | user1 | user2 | ...
    index = 1
    col = 0
    for exercise in exercises:
        submissions = Submissions.objects.filter(classes=Cpk).filter(exercises=exercise.pk)
        grades.append([exercise.name,])
        for student in students:
            # check if student submitted an answer for this exercise
            submitted = submissions.filter(student=student).values_list('submitted',flat=True).first()
            # decide if user got the correct answer or not (zero if not submitted)
            answer = generate_hash.gen(student, exercise, classes.instructor.first())
            if not submitted:
                print("They didn't submit")
                grades[index].append("0")
            elif submitted == answer:
                print("they are right")
                grades[index].append("1")
                percentages[col][0] += 1
            else:
                print("they are wrong")
                grades[index].append("0")
            percentages[col][1] += 1
            col += 1
        col = 0
        index += 1
    # append percentage to last row
    grades.append(["Percentage",])
    for i in range(0,columns):
        score = percentages[i][0] / percentages[i][1]
        score = score * 100
        grades[index].append(score)
    return grades

@login_required
def GradebookView(request, Cpk):
    if request.user.is_superuser == True:
        classes = Classes.objects.get(pk=Cpk)
        grades  = getGrades(Cpk)
        return render(request, 'details_gradebook.html', {'classes': classes, 'grades':grades,})

@login_required
def GradebookEmail(request, Cpk):
    if request.user.is_superuser == True:
        # get grades
        grades = getGrades(Cpk)
        # returns if it was successful or not
        status = send_mail.send_grades(Cpk, grades, request)
        return render(request, 'gradebook_email_status.html', {'status':status})

# Viewing Database Items
@login_required
def StudentsView(request):
    if request.user.is_superuser == True:
        students = CustomUser.objects.all()
        return render(request, 'details_students.html', {'students': students})
@login_required
def ExercisesView(request):
    if request.user.is_superuser == True:
        exercises = Exercises.objects.all()
        return render(request, 'details_exercises.html', {'exercises': exercises})
@login_required
def ClassesView(request):
    if request.user.is_superuser == True:
        classes = Classes.objects.all()
        return render(request, 'details_classes.html', {'classes': classes})

# Editing Database Items
@method_decorator(login_required, name='dispatch')
class ClassesCreate(CreateView):
    model = Classes
    fields = '__all__'

@method_decorator(login_required, name='dispatch')
class ClassesUpdate(UpdateView):
    model = Classes
    fields = '__all__'

@method_decorator(login_required, name='dispatch')
class ClassesDelete(DeleteView):
    model = Classes
    fields = '__all__'
    success_url = reverse_lazy('instructor')

@method_decorator(login_required, name='dispatch')
class ClassesDetailView(generic.DetailView):
    model = Classes

@method_decorator(login_required, name='dispatch')
class ExercisesCreate(CreateView):
    model = Exercises
    fields = '__all__'

@method_decorator(login_required, name='dispatch')
class ExercisesUpdate(UpdateView):
    model = Exercises
    fields = '__all__'

@method_decorator(login_required, name='dispatch')
class ExercisesDelete(DeleteView):
    model = Exercises
    fields = '__all__'
    success_url = reverse_lazy('instructor')

@method_decorator(login_required, name='dispatch')
class ExercisesDetailView(generic.DetailView):
    model = Exercises

@method_decorator(login_required, name='dispatch')
class CustomUserCreate(CreateView):
    model = CustomUser
    fields = '__all__'

@method_decorator(login_required, name='dispatch')
class CustomUserUpdate(UpdateView):
    model = CustomUser
    fields = '__all__'

@method_decorator(login_required, name='dispatch')
class CustomUserDelete(DeleteView):
    model = CustomUser
    fields = '__all__'
    success_url = reverse_lazy('instructor')

@method_decorator(login_required, name='dispatch')
class StudentsDetailView(generic.DetailView):
    model = CustomUser

@method_decorator(login_required, name='dispatch')
class SettingsUpdate(UpdateView):
    model = Settings
    fields = '__all__'
    success_url = reverse_lazy('update_settings')

@login_required
def UpdateSettings(request):
    if request.user.is_superuser == True:
        setting = Settings.objects.get(pk=1)
        update_settings.update_instances(setting.instances)
        update_settings.update_ram_and_cpu(setting.ram,setting.cores)
        return redirect('instructor')

@method_decorator(login_required, name='dispatch')
class SettingsDetailView(generic.DetailView):
    model = Settings

@login_required
def StartExercise(request, StudentPK, ExercisePK, ClassPK):
    # ensure the user has authorization to start that exercise
    classes = Classes.objects.get(pk=ClassPK)
    student = CustomUser.objects.get(pk=StudentPK)
    # finds student and their exercise to run
    exercise = Exercises.objects.get(pk=ExercisePK)
    exercise_name = exercise.name
    exercise_name = exercise_name.lower()
    exercise_name = exercise_name.replace(" ", "")
    student_name = student.username

    # ensure the student isn't already running another container
    if student.exercise_running is not None:
        return redirect('student')

    # run the exercise
    # pass in answer to that container
    answer = generate_hash.gen(student, exercise, classes.instructor.first())
    status = command.run_container(student_name, exercise_name, answer)

    # update containers running if it staretd successfully
    if(status != 1):
        student.exercise_running = Exercises.objects.get(pk=ExercisePK)
        student.exercise_port = status
        student.save()
    print("Exercises open: "+str(student.exercise_running.name))
    # give the user back their port so they know where to go
    return redirect('student')

@login_required
def StopExercise(request, StudentPK, ExercisePK):
    # ensure the user has authorization to start that exercise
    student = CustomUser.objects.get(pk=StudentPK)
    # finds student and their exercise to run
    exercise = Exercises.objects.get(pk=ExercisePK)
    exercise_name = exercise.name
    exercise_name = exercise_name.lower()
    exercise_name = exercise_name.replace(" ", "")
    student_name = student.username

    # run the exercise
    status = command.stop_container(student_name, exercise_name)

    # update containers stopped successfully
    if(status == 0):
        student.exercise_running = None
        student.save()
    return redirect('student')

@login_required
def RestartExercise(request, StudentPK, ExercisePK, ClassPK):
    # ensure the user has authorization to start that exercise
    classes = Classes.objects.get(pk=ClassPK)
    student = CustomUser.objects.get(pk=StudentPK)
    # finds student and their exercise to run
    exercise = Exercises.objects.get(pk=ExercisePK)
    exercise_name = exercise.name
    exercise_name = exercise_name.lower()
    exercise_name = exercise_name.replace(" ", "")
    student_name = student.username

    # restart the exercise
    answer = generate_hash.gen(student, exercise, classes.instructor.first())
    status = command.restart_container(student_name, exercise_name, answer)

    # update containers running if it staretd successfully
    if(status != 0):
        student.exercise_running = Exercises.objects.get(pk=ExercisePK)
        student.exercise_port = status
        student.save()
    print("Exercises open: "+str(student.exercise_running.name))
    return redirect('student')

# Sample data to interact with
def create_data():
    u4 = CustomUser.objects.create_user('johndoe', 'myemail@crazymail.com', 'johndoe')
    u4.first_name = 'John'
    u4.last_name = 'Doe'
    u4.save()
    u5 = CustomUser.objects.create_user('dumby', 'myemail@crazymail.com', 'dumby')
    u5.first_name = 'Dumby'
    u5.last_name = 'Dumbdumb'
    u5.save()
    u6 = CustomUser.objects.create_user('packman', 'so87@evansville.edu', 'packman')
    u6.first_name = 'Packman'
    u6.last_name = 'Jones'
    u6.save()
    u1 = CustomUser.objects.create_superuser('mark', 'myemail@crazymail.com', 'mark')
    u1.first_name = 'mark'
    u1.last_name = 'randall'
    u1.save()
    u2 = CustomUser.objects.create_superuser('deborah', 'myemail@crazymail.com', 'deborah')
    u2.first_name = 'deborah'
    u2.last_name = 'hwang'
    u2.save()
    u3 = CustomUser.objects.create_superuser('ron', 'myemail@crazymail.com', 'doberts')
    u3.first_name = 'ron'
    u3.last_name = 'doberts'
    u3.save()


    wa1 = Exercises.objects.create(name='Weak Auth 1', description='The login page is broken! Find out how to get the secret key!')
    wa1.save()
    wa2 = Exercises.objects.create(name='Weak Auth 2', description='How does the login page work?')
    wa2.save()
    wa3 = Exercises.objects.create(name='Weak Auth 3', description='You might be able to execute some privileged actions')
    wa3.save()
    cwa1 = Exercises.objects.create(name='C_Weak Auth 1', description='The application has hard coded credentials.')
    cwa1.save()
    e3 = Exercises.objects.create(name='XSS 1', description='Bypass the HTML input filter. An admin is trying to login every 30seconds!')
    e3.save()

    e1 = Exercises()
    e1.name = 'SQL Injection'
    e1.description = 'Give an example of SQL injection on port 8882'
    e1.save()
    e2 = Exercises()
    e2.name = 'SQL Injection 2'
    e2.description = 'Give an example of SQL injection on port 12834'
    e2.save()
    e4 = Exercises()
    e4.name = 'Buffer Overflow'
    e4.description = 'Give an example of Buffer overflow on port 8812'
    e4.save()

    c2 = Classes()
    c2.name = 'Desktop Security Fall 2018'
    c2.description = 'Taught by Mr. Randall'
    c2.save()
    c2.instructor.add(u1)
    c2.exercises.add(e3)
    c2.exercises.add(wa1)
    c2.exercises.add(wa2)
    c2.exercises.add(wa3)
    c2.exercises.add(cwa1)
    c2.students.add(u4)
    c2.students.add(u5)
    c2.students.add(u6)
    c2.save()
    c1 = Classes()
    c1.name = 'Desktop Security Fall 2017'
    c1.description = 'Taught by Ron Doberts'
    c1.save()
    c1.instructor.add(u2)
    c1.exercises.add(e1)
    c1.exercises.add(e2)
    c1.students.add(u4)
    c1.students.add(u5)
    c1.save()
    c3 = Classes()
    c3.name = 'Web Security Spring 2019'
    c3.description = 'Taught by Dr. Hwang'
    c3.save()
    c3.instructor.add(u2)
    c3.exercises.add(e1)
    c3.exercises.add(e2)
    c3.exercises.add(e4)
    c3.students.add(u4)
    c3.students.add(u6)
    c3.save()

    s = Settings()
    s.name = "Settings"
    s.hostname = "localhost"
    s.ram = "4000"
    s.cores = "4"
    s.instances = "4"
    s.save()
    

def DataView(request):
    create_data()
    return render(request, 'create_data.html')