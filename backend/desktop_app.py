import cv2
import face_recognition
import os
from PIL import Image, ImageTk, ImageFilter
import numpy as np
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime
import csv
import random
import string

# Directory paths
student_images_dir = 'D:\\Attendanceface\\student_images'
attendance_file = 'attendance.csv'
registered_students_file = 'registered_students.csv'
os.makedirs(student_images_dir, exist_ok=True)


def convert_image_to_rgb(image_path):
    try:
        with Image.open(image_path) as img:
            if img.mode != 'RGB':
                rgb_image = img.convert('RGB')
                rgb_image.save(image_path, format='JPEG')  # Save as JPEG to ensure compatibility
    except Exception as e:
        print(f"Error converting image {image_path}: {e}")


def capture_photo(student_name, roll_number):
    video_capture = cv2.VideoCapture(0)
    if not video_capture.isOpened():
        raise RuntimeError("Cannot access the webcam.")

    while True:
        ret, frame = video_capture.read()
        if not ret:
            raise RuntimeError("Failed to capture image.")

        # Show the frame to the user
        cv2.imshow('Adjust Your Face and Press Q to Capture', frame)

        # Wait for user to press 'q' to capture the photo
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    image_filename = os.path.join(student_images_dir, f'{student_name}_{roll_number}.jpg')
    cv2.imwrite(image_filename, frame)

    # Convert captured image to RGB
    convert_image_to_rgb(image_filename)

    video_capture.release()
    cv2.destroyAllWindows()

    return image_filename


def generate_verification_code():
    # Generate a code starting with "IT" followed by a 4-digit number
    return f"IT{random.randint(1, 1000):04d}"


def register_student():
    name = entry_name.get()
    roll_no = entry_roll_no.get()

    if not name or not roll_no:
        messagebox.showerror("Error", "Please enter name and roll number.")
        return

    verification_code = generate_verification_code()
    image_filename = capture_photo(name, roll_no)

    with open(registered_students_file, 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([name, roll_no, verification_code, image_filename])

    messagebox.showinfo("Success",
                        f"Student {name} with Roll No {roll_no} successfully registered.\nVerification Code: {verification_code}")
    update_student_list()


def verify_student():
    name = entry_verify_name.get()
    roll_no = entry_verify_roll_no.get()
    verification_code = entry_verify_code.get()

    if not name or not roll_no or not verification_code:
        messagebox.showerror("Error", "Please enter name, roll number, and verification code.")
        return

    found = False
    registered_image_filename = None
    with open(registered_students_file, 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            registered_name, registered_roll_no, registered_code, registered_image_filename = row
            if (registered_name == name and
                    registered_roll_no == roll_no and
                    registered_code == verification_code):
                found = True
                break

    if not found:
        messagebox.showerror("Error", "Verification failed. Check details and code.")
        return

    video_capture = cv2.VideoCapture(0)
    if not video_capture.isOpened():
        messagebox.showinfo("Error", "Cannot access the webcam.")
        return

    while True:
        ret, frame = video_capture.read()
        if not ret:
            messagebox.showinfo("Error", "Failed to capture image.")
            break

        # Show the frame to the user
        cv2.imshow('Verification - Adjust Your Face and Press Q to Capture', frame)

        # Wait for user to press 'q' to capture the photo
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    if ret:
        # Save and inspect the captured image
        test_image_path = os.path.join(student_images_dir, 'test_image.jpg')
        cv2.imwrite(test_image_path, frame)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        try:
            face_locations = face_recognition.face_locations(rgb_frame, model="hog")
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations, num_jitters=2)
        except Exception as e:
            messagebox.showinfo("Error", f"Face recognition failed: {e}")
            video_capture.release()
            cv2.destroyAllWindows()
            return

        if not face_locations:
            messagebox.showinfo("Error", "No face locations found. Verification failed.")
            video_capture.release()
            cv2.destroyAllWindows()
            return

        if not face_encodings:
            messagebox.showinfo("Error", "No face encodings found. Verification failed.")
            video_capture.release()
            cv2.destroyAllWindows()
            return

        # Load known face encodings
        registered_image = face_recognition.load_image_file(registered_image_filename)
        registered_face_encodings = face_recognition.face_encodings(registered_image)
        if not registered_face_encodings:
            messagebox.showinfo("Error", "No face encodings found for the registered student.")
            return

        registered_face_encoding = registered_face_encodings[0]

        match_found = False
        for face_encoding in face_encodings:
            matches = face_recognition.compare_faces([registered_face_encoding], face_encoding)
            face_distances = face_recognition.face_distance([registered_face_encoding], face_encoding)
            best_match_index = np.argmin(face_distances)

            if matches[best_match_index] and face_distances[best_match_index] < 0.6:  # Set a threshold for face distance
                match_found = True
                messagebox.showinfo("Success", f"Student {name} is verified.")
                mark_attendance(name, roll_no)
                break

        if not match_found:
            messagebox.showinfo("Error", "No matching face found. Verification failed.")

    video_capture.release()
    cv2.destroyAllWindows()


def mark_attendance(name, roll_no):
    with open(attendance_file, 'a', newline='') as f:
        now = datetime.now()
        dt_string = now.strftime('%Y-%m-%d %H:%M:%S')
        f.write(f'{name},{roll_no},{dt_string}\n')


def update_student_list():
    # Clear the existing items in the treeview
    tree.delete(*tree.get_children())

    # Read the CSV file and populate the treeview
    with open(registered_students_file, 'r') as file:
        reader = csv.reader(file)
        for index, row in enumerate(reader):
            # Use a unique identifier by combining index and roll number
            unique_id = f"{index}_{row[1]}"
            tree.insert('', 'end', iid=unique_id, values=row[:3])


def remove_student(unique_id):
    # Extract roll number from unique_id
    roll_no = unique_id.split('_')[1]

    # Read the CSV file and filter out the student to be removed
    updated_rows = []
    student_image_filename = None
    with open(registered_students_file, 'r') as file:
        reader = csv.reader(file)
        for row in reader:
            if row[1] == roll_no:
                student_image_filename = row[3]  # Get the image filename
            else:
                updated_rows.append(row)

    # Write the filtered data back to the CSV file
    with open(registered_students_file, 'w', newline='') as file:
        writer = csv.writer(file)
        writer.writerows(updated_rows)

    # Delete the student's image file if it exists
    if student_image_filename and os.path.exists(student_image_filename):
        os.remove(student_image_filename)

    messagebox.showinfo("Success", f"Student with Roll No {roll_no} has been removed.")
    update_student_list()


def create_pill_button(parent, text, command):
    button = tk.Button(parent, text=text, command=command, font=('Arial', 10), bg="#ffffff", fg="#2c3e50", bd=0,
                       relief="flat", padx=20, pady=5)
    button.bind("<Enter>", lambda e: button.config(bg="#ecf0f1"))
    button.bind("<Leave>", lambda e: button.config(bg="#ffffff"))
    return button


def create_frosted_glass_background(root, width, height):
    # Create a transparent image
    background_image = Image.new("RGBA", (width, height), (255, 255, 255, 0))

    # Apply a blur effect
    background_image = background_image.filter(ImageFilter.GaussianBlur(10))

    # Add a semi-transparent white overlay
    overlay = Image.new("RGBA", background_image.size, (255, 255, 255, 127))  # 50% transparency
    background_image = Image.alpha_composite(background_image, overlay)

    # Convert to a format that tkinter can use
    return ImageTk.PhotoImage(background_image)


def create_main_menu():
    frame_main_menu = ttk.Frame(notebook)
    notebook.add(frame_main_menu, text="Home")

    tk.Label(frame_main_menu, text="Student Registration and Verification System", font=('Arial', 18)).pack(pady=20)
    create_pill_button(frame_main_menu, "Register Student", lambda: notebook.select(frame_register)).pack(pady=10)
    create_pill_button(frame_main_menu, "Verify Student", lambda: notebook.select(frame_verify)).pack(pady=10)
    create_pill_button(frame_main_menu, "Registered Students", lambda: notebook.select(frame_list)).pack(pady=10)


# Main application window
root = tk.Tk()
root.title("Student Registration and Verification")
root.geometry("1000x700")

# Creating the frosted glass background
background_image = create_frosted_glass_background(root, 1000, 700)
background_label = tk.Label(root, image=background_image)
background_label.place(x=0, y=0, relwidth=1, relheight=1)

# Creating a glass-like frame
glass_frame = tk.Frame(root, bg="#ffffff", bd=1, relief="solid")
glass_frame.place(x=150, y=100, width=500, height=500)

# Creating the left-side taskbar
taskbar = tk.Frame(root, bg="#2c3e50", width=200)
taskbar.pack(side="left", fill="y")

# Creating the main content area
content_frame = tk.Frame(root, bg="#ffffff", bd=0)
content_frame.pack(side="right", fill="both", expand=True)

notebook = ttk.Notebook(content_frame)
notebook.pack(pady=10, expand=True)

create_main_menu()

frame_register = ttk.Frame(notebook)
notebook.add(frame_register, text="Register Student")

tk.Label(frame_register, text="Register Student", font=('Arial', 14)).grid(row=0, column=0, columnspan=2, pady=10)

tk.Label(frame_register, text="Name").grid(row=1, column=0, sticky="e")
entry_name = tk.Entry(frame_register)
entry_name.grid(row=1, column=1)

tk.Label(frame_register, text="Roll No").grid(row=2, column=0, sticky="e")
entry_roll_no = tk.Entry(frame_register)
entry_roll_no.grid(row=2, column=1)

btn_register_student = create_pill_button(frame_register, "Register", register_student)
btn_register_student.grid(row=3, column=0, columnspan=2, pady=10)

frame_verify = ttk.Frame(notebook)
notebook.add(frame_verify, text="Verify Student")

tk.Label(frame_verify, text="Verify Student", font=('Arial', 14)).grid(row=0, column=0, columnspan=2, pady=10)

tk.Label(frame_verify, text="Name").grid(row=1, column=0, sticky="e")
entry_verify_name = tk.Entry(frame_verify)
entry_verify_name.grid(row=1, column=1)

tk.Label(frame_verify, text="Roll No").grid(row=2, column=0, sticky="e")
entry_verify_roll_no = tk.Entry(frame_verify)
entry_verify_roll_no.grid(row=2, column=1)

tk.Label(frame_verify, text="Verification Code").grid(row=3, column=0, sticky="e")
entry_verify_code = tk.Entry(frame_verify)
entry_verify_code.grid(row=3, column=1)

btn_verify_student = create_pill_button(frame_verify, "Verify", verify_student)
btn_verify_student.grid(row=4, column=0, columnspan=2, pady=10)

frame_list = ttk.Frame(notebook)
notebook.add(frame_list, text="Registered Students")

tree = ttk.Treeview(frame_list, columns=("Name", "Roll No", "Code"), show="headings")
tree.heading("Name", text="Name")
tree.heading("Roll No", text="Roll No")
tree.heading("Code", text="Verification Code")
tree.pack(fill="both", expand=True)

tree.bind("<Delete>", lambda event: remove_student(tree.focus()))

# Load the student list at startup
update_student_list()

root.mainloop()
