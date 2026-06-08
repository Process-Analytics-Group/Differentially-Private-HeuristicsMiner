# Standard Library Imports
import os
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk

# Third-Party Imports
from PIL import Image, ImageTk

# Local Imports
from DPHM import DPHM


class GUI:
    def __init__(self):
        # <editor-fold desc="# Main GUI">
        self.root = tk.Tk()
        self.root.title("Differentially Private HeuristicMiner")
        self.root.geometry("1640x1240")
        self.DPHM = DPHM(self)
        # </editor-fold>

        # <editor-fold desc="# Canvas">
        self.canvas_data = {}

        canvas_width = 1240
        canvas_height = 600

        positions = [(0, 0), (0, 620)]  # top, bottom
        for i, (x, y) in enumerate(positions, start=1):
            canvas = tk.Canvas(self.root, bg="white", width=canvas_width, height=canvas_height)
            canvas.place(x=x, y=y)

            self.canvas_data[i] = {
                "image_tk": None,
                "original_image": None,
                "displayed_image": None,
                "scale_factor": 1.0,
                "pan_x": 0,
                "pan_y": 0,
                "start_x": None,
                "start_y": None,
                "canvas": canvas
            }

        for idx in (1, 2):
            self.canvas_data[idx]["canvas"].bind("<Left>", lambda e, i=idx: self.pan_image_keyboard(-20, 0, i))
            self.canvas_data[idx]["canvas"].bind("<Right>", lambda e, i=idx: self.pan_image_keyboard(20, 0, i))
            self.canvas_data[idx]["canvas"].bind("<Up>", lambda e, i=idx: self.pan_image_keyboard(0, -20, i))
            self.canvas_data[idx]["canvas"].bind("<Down>", lambda e, i=idx: self.pan_image_keyboard(0, 20, i))

            # Zoom
            self.canvas_data[idx]["canvas"].bind(
                "<MouseWheel>",
                lambda event, i=idx: self.zoom_canvas(event, self.canvas_data[i], i)
            )

            # Pan (mouse drag)
            self.canvas_data[idx]["canvas"].bind(
                "<ButtonPress-1>",
                lambda event, i=idx: self.start_pan(event, self.canvas_data[i])
            )
            self.canvas_data[idx]["canvas"].bind(
                "<B1-Motion>",
                lambda event, i=idx: self.pan_image(event, self.canvas_data[i], i)
            )
        # </editor-fold>

        # <editor-fold desc="# Canvas labels">
        self.canvas_label_1 = tk.Label(self.root, text="Dependency Graph", font=("Helvetica", 14, "bold"), fg="black")
        self.canvas_label_1.place(x=10, y=10)

        # self.canvas_label_3 = tk.Label(self.root, text="BPMN", font=("Helvetica", 14, "bold"), fg="black")
        self.canvas_label_3 = tk.Label(self.root, text="Petri Net", font=("Helvetica", 14, "bold"), fg="black")
        self.canvas_label_3.place(x=10, y=630)

        # </editor-fold>

        # <editor-fold desc="# Separators to separate the canvases">
        self.separator1 = ttk.Separator(self.root, orient="horizontal")
        self.separator1.place(x=0, y=610, width=1220)
        # </editor-fold>

        # <editor-fold desc="# File Open Button and Label">
        self.open_button = ttk.Button(self.root, text="Open File...", command=self.open_file)
        self.open_button.place(x=1280, y=10)
        self.filename_label = ttk.Label(self.root, text="")
        self.filename_label.place(x=1380, y=15)
        # </editor-fold>

        # <editor-fold desc="# Dropdown menu for rejection sampling attribute">
        self.rejection_sampling_attr = tk.StringVar()
        self.rejection_label = ttk.Label(self.root, text="Rejection Sampling Attribute:")
        self.rejection_label.place(x=1280, y=90)
        self.rejection_dropdown = ttk.Combobox(self.root, textvariable=self.rejection_sampling_attr, state="readonly")
        self.rejection_dropdown["values"] = ("No Rejection Sampling", "F1-Score", "Fitness", "Precision", "Simplicity", "Generalization")
        self.rejection_dropdown.place(x=1450, y=90)
        self.rejection_dropdown.bind("<<ComboboxSelected>>", self.update_rejection_attr)
        self.rejection_dropdown.current(0)  # Selects 'F1-Score'
        # </editor-fold>

        # <editor-fold desc="# Rejection Sampling Threshold Value">
        self.rejection_threshold = tk.DoubleVar(value=0.0)
        self.threshold_value_label = ttk.Label(self.root, text="Rejection Sampling Threshold:")
        self.threshold_value_label.place(x=1280, y=135)
        self.threshold_value_slider = tk.Scale(self.root, from_=0.0, to=1.0, resolution=0.01, orient='horizontal',
                                               variable=self.rejection_threshold, command=self.update_rejection_value)
        self.threshold_value_slider.place(x=1450, y=115, width=140)
        self.threshold_value_slider.bind("<ButtonRelease-1>", self.action_slider)
        # </editor-fold>

        # <editor-fold desc="# Separator between Rejection Sampling and sliders">
        self.separator4 = ttk.Separator(self.root, orient="horizontal")
        self.separator4.place(x=1270, y=170, width=320)
        # </editor-fold>

        # <editor-fold desc="# Epsilon Slider">
        self.epsilon = tk.DoubleVar(value=5.0)
        self.epsilon_label = ttk.Label(self.root, text="Epsilon")
        self.epsilon_label.place(x=1265, y=190)

        self.epsilon_slider = tk.Scale(self.root, from_=5, to=0.01, resolution=0.01, orient="vertical",
                                       variable=self.epsilon, command=self.update_epsilon)
        self.epsilon_slider.place(x=1260, y=210, height=200)
        self.epsilon_slider.bind("<ButtonRelease-1>", self.action_epsilon_slider)
        # </editor-fold>

        # <editor-fold desc="# Dependency Slider">
        self.dependency = tk.DoubleVar(value=-1)
        self.dependency_label = ttk.Label(self.root, text="Dependency")
        self.dependency_label.place(x=1330, y=190)

        self.dependency_slider = tk.Scale(self.root, from_=1, to=-1, resolution=0.01, orient="vertical",
                                          variable=self.dependency, command=self.update_dependency)
        self.dependency_slider.place(x=1330, y=210, height=200)
        self.dependency_slider.bind("<ButtonRelease-1>", self.action_slider)
        # </editor-fold>

        # <editor-fold desc="# AND Slider">
        self.AND = tk.DoubleVar(value=0.0)
        self.AND_label = ttk.Label(self.root, text="And")
        self.AND_label.place(x=1420, y=190)

        self.AND_slider = tk.Scale(self.root, from_=1, to=0.01, resolution=0.01, orient="vertical",
                                   variable=self.AND, command=self.update_and)
        self.AND_slider.place(x=1400, y=210, height=200)
        self.AND_slider.bind("<ButtonRelease-1>", self.action_slider)
        # </editor-fold>

        # <editor-fold desc="# Pre-Noise Slider">
        self.pre_noise = tk.DoubleVar(value=0.0)
        self.pre_noise_label = ttk.Label(self.root, text="Noise")
        self.pre_noise_label.place(x=1480, y=190)

        self.pre_noise_slider = tk.Scale(self.root, from_=1, to=0.01, resolution=0.01, orient="vertical",
                                         variable=self.pre_noise, command=self.update_pre_noise)
        self.pre_noise_slider.place(x=1470, y=210, height=200)
        self.pre_noise_slider.bind("<ButtonRelease-1>", self.action_slider)
        # </editor-fold>

        # <editor-fold desc="# Loop2 Slider">
        self.loop2 = tk.DoubleVar(value=0.0)
        self.loop2_label = ttk.Label(self.root, text="Loop")
        self.loop2_label.place(x=1550, y=190)

        self.loop2_slider = tk.Scale(self.root, from_=1, to=0.01, resolution=0.01, orient="vertical",
                                     variable=self.loop2, command=self.update_loop2)
        self.loop2_slider.place(x=1540, y=210, height=200)
        self.loop2_slider.bind("<ButtonRelease-1>", self.action_slider)
        # </editor-fold>

        # <editor-fold desc="# Min_DFG_Count input">
        self.min_dfg = tk.DoubleVar(value=1)
        self.min_dfg_button = ttk.Button(self.root, text="Set min. count of DFG", command=self.update_min_dfg)
        self.min_dfg_button.place(x=1280, y=440)

        self.min_dfg_label = tk.Entry(self.root, textvariable=self.min_dfg, state='disabled',
                                      font=('Arial', 14), justify='center', width=10)
        self.min_dfg_label.place(x=1470, y=440)
        # </editor-fold>

        # <editor-fold desc="# Min_Act_Count input">
        self.min_act = tk.DoubleVar(value=1)
        self.min_act_button = ttk.Button(self.root, text="Set min. count of Activities", command=self.update_min_act)
        self.min_act_button.place(x=1280, y=480)

        self.min_act_label = tk.Entry(self.root, textvariable=self.min_act, state='disabled',
                                      font=('Arial', 14), justify='center', width=10)
        self.min_act_label.place(x=1470, y=480)
        # </editor-fold>

        # <editor-fold desc="# Separator between sliders and Save / Quit buttons">
        self.separator5 = ttk.Separator(self.root, orient="horizontal")
        self.separator5.place(x=1270, y=570, width=320)
        # </editor-fold>

        # <editor-fold desc="# Save / Quit buttons">
        self.save_dg_button = ttk.Button(self.root, text="Save DG", command=lambda: self.save_canvas_image(1))
        self.save_dg_button.place(x=1275, y=580)

        self.save_pn_button = ttk.Button(self.root, text="Save PN", command=lambda: self.save_canvas_image(2))
        self.save_pn_button.place(x=1365, y=580)

        self.quit_button = ttk.Button(self.root, text="Quit", command=self.root.quit)
        self.quit_button.place(x=1455, y=580)
        # </editor-fold>

    def open_file(self):
        """Opens a file dialog for .xes files and updates the label."""
        file_path = filedialog.askopenfilename(filetypes=[("XES Files", "*.xes")])

        if file_path:
            filename = os.path.basename(file_path)
            self.filename_label.config(text=f"{filename}")
            self.DPHM.add_event_log(file_path)

    def update_rejection_attr(self, value):
        """Updates self.rejection_sampling_attr when dropdown selection changes."""
        selected_value = self.rejection_sampling_attr.get()
        self.rejection_dropdown.set(selected_value)  # Manually update display
        self.rejection_dropdown.update()  # Force redraw
        self.DPHM.rejection_sampling(renoise=False)

    def update_rejection_value(self, value):
        self.rejection_threshold.set(value)
        # self.DPHM.rejection_sampling(renoise=False)

    def update_min_dfg(self):
        new_value = simpledialog.askstring("Input", "Enter a new non-negative integer value:")
        if new_value is not None:
            if self.is_positive_integer(new_value):
                self.min_dfg.set(int(new_value))
                self.DPHM.rejection_sampling(renoise=False)
            else:
                messagebox.showerror("Invalid Input", "Please enter a valid non-negative integer.")

    def update_min_act(self):
        new_value = simpledialog.askstring("Input", "Enter a new non-negative integer value:")
        if new_value is not None:
            if self.is_positive_integer(new_value):
                self.min_act.set(int(new_value))
                self.DPHM.rejection_sampling(renoise=False)
            else:
                messagebox.showerror("Invalid Input", "Please enter a valid non-negative integer.")

    @staticmethod
    def is_positive_integer(value):
        try:
            return int(value) >= 0
        except ValueError:
            return False

    def update_epsilon(self, value):
        """Updates epsilon when the slider changes."""
        self.epsilon.set(value)

    def update_dependency(self, value):
        """Updates epsilon when the slider changes."""
        self.dependency.set(value)

    def update_and(self, value):
        """Updates epsilon when the slider changes."""
        self.AND.set(value)

    def update_pre_noise(self, value):
        """Updates epsilon when the slider changes."""
        self.pre_noise.set(value)

    def update_loop2(self, value):
        """Updates epsilon when the slider changes."""
        self.loop2.set(value)

    def action_epsilon_slider(self, value):
        self.DPHM.rejection_sampling()

    def action_slider(self, value):
        self.DPHM.rejection_sampling(renoise=False)

    def apply_image(self, img, canvas):
        """Assign an image to a specific canvas."""
        data = self.canvas_data[canvas]
        data["original_image"] = img
        data["scale_factor"] = 1.0
        data["pan_x"] = 0
        data["pan_y"] = 0
        self.display_image(canvas)

    def display_image(self, canvas):
        """Display the image on the given canvas."""
        data: tk.Canvas = self.canvas_data[canvas]
        if data["original_image"] is None:
            return

        # Resize image according to zoom factor
        new_width = int(data["original_image"].width * data["scale_factor"])
        new_height = int(data["original_image"].height * data["scale_factor"])

        if new_width < 20 or new_height < 20:
            return  # Prevent image from shrinking too much

        # Resize from the original image
        data["displayed_image"] = data["original_image"].resize((new_width, new_height), Image.LANCZOS)
        data["image_tk"] = ImageTk.PhotoImage(data["displayed_image"])

        # Clear canvas and redraw image
        self.canvas_data[canvas]["canvas"].delete("all")
        self.canvas_data[canvas]["canvas"].create_image(
            new_width // 2 + data["pan_x"],
            new_height // 2 + data["pan_y"],
            image=data["image_tk"],
            tags="zoomable"
        )

    def zoom_canvas(self, event, data, i):
        """Zoom in or out for a specific canvas using the mouse wheel."""

        if event.delta > 0:
            data["scale_factor"] /= 1.1  # Zoom out
        else:
            data["scale_factor"] *= 1.1  # Zoom in

        # Keep zoom factor within reasonable limits
        data["scale_factor"] = max(0.1, min(5.0, data["scale_factor"]))

        self.display_image(i)

    def save_canvas_image(self, canvas_id):
        data = self.canvas_data[canvas_id]

        if data["displayed_image"] is None:
            messagebox.showwarning("No Image", "There is no image to save yet.")
            return

        file_path = filedialog.asksaveasfilename(
            defaultextension=".jpg",
            filetypes=[
                ("JPEG files", "*.jpg"),
                ("PNG files", "*.png"),
                ("All files", "*.*")
            ]
        )

        if not file_path:
            return

        try:
            image = data["displayed_image"]

            if file_path.lower().endswith((".jpg", ".jpeg")):
                image = image.convert("RGB")

            image.save(file_path)

        except Exception as e:
            messagebox.showerror("Save Error", f"Image could not be saved: {e}")

    @staticmethod
    def start_pan(event, data):
        """Start panning when left mouse button is pressed."""
        data["start_x"] = event.x
        data["start_y"] = event.y

    def pan_image(self, event, data, i):
        """Pan the image by dragging the mouse."""
        dx = event.x - data["start_x"]
        dy = event.y - data["start_y"]
        data["pan_x"] += dx
        data["pan_y"] += dy
        data["start_x"] = event.x
        data["start_y"] = event.y
        self.display_image(i)

    def pan_image_keyboard(self, dx, dy, i):
        data = self.canvas_data[i]
        data["pan_x"] += dx
        data["pan_y"] += dy
        self.display_image(i)


if __name__ == '__main__':
    app = GUI()
    app.root.mainloop()
