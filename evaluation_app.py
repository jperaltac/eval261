"""
Simple evaluation application using Tkinter.

This script loads an official rubric and a list of students from JSON files
and provides a graphical interface to assign performance levels for each
criterion to a selected student. The application computes the weighted
score and translates it into a final grade on a 1–7 scale. Evaluations
are saved locally and can be reopened for editing.

Files used:
  - rubric.json: list of criteria with weights and level descriptions.
  - students.json: list of students with identifiers and names.
  - evaluations/: directory where completed evaluations are saved as JSON.

To run the application, execute this script with Python 3. It requires
no external dependencies beyond Tkinter, which ships with the standard
Python distribution. The GUI is intentionally simple and avoids the
complexities of heavy web frameworks.
"""

import json
import os
import datetime
import tkinter as tk
from tkinter import ttk, messagebox


class EvaluationApp:
    """Main application class for student evaluation."""

    def __init__(self, master: tk.Tk, data_dir: str = "."):
        self.master = master
        self.master.title("Evaluación de Estudiantes")
        self.data_dir = data_dir

        # Load rubric and students
        rubric_path = os.path.join(data_dir, "rubric.json")
        students_path = os.path.join(data_dir, "students.json")
        if not os.path.isfile(rubric_path) or not os.path.isfile(students_path):
            messagebox.showerror(
                "Error", "No se encontraron los archivos rubric.json o students.json en " + data_dir
            )
            self.master.destroy()
            return

        with open(rubric_path, "r", encoding="utf-8") as f:
            self.rubric = json.load(f)

        with open(students_path, "r", encoding="utf-8") as f:
            self.students = json.load(f)

        # Ensure evaluations directory exists
        self.evals_dir = os.path.join(data_dir, "evaluations")
        os.makedirs(self.evals_dir, exist_ok=True)

        # Mapping from performance level code to numeric score (0-1)
        # Values based on the ranges specified in the rubric: SD (≤0.25), DI (0.26–0.5), DS (0.51–0.75), DD (0.76–1)
        self.level_values = {
            "DD": 1.0,   # Destacado
            "DS": 0.75,  # Satisfactorio
            "DI": 0.5,   # Insuficiente
            "SD": 0.25   # Sin Dominio
        }

        # Current selections for each criterion
        self.selections = {}
        self.current_student_id = None

        # Build the user interface
        self._build_ui()

    def _build_ui(self) -> None:
        """Construct the GUI layout."""
        # Main container frames
        container = ttk.Frame(self.master, padding=10)
        container.pack(fill=tk.BOTH, expand=True)

        left_frame = ttk.Frame(container)
        left_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))

        right_frame = ttk.Frame(container)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Student list label and listbox
        ttk.Label(left_frame, text="Estudiantes").pack(anchor=tk.W)
        self.student_listbox = tk.Listbox(left_frame, height=20, exportselection=False)
        for student in self.students:
            self.student_listbox.insert(tk.END, student["name"])
        self.student_listbox.pack(fill=tk.BOTH, expand=True)
        self.student_listbox.bind("<<ListboxSelect>>", self.on_student_select)

        # Scrollable canvas for criteria
        self.canvas = tk.Canvas(right_frame, borderwidth=0)
        self.criteria_frame = ttk.Frame(self.canvas)
        self.vscrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.vscrollbar.set)
        self.vscrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        # Create a window in canvas
        self.canvas_frame = self.canvas.create_window((0, 0), window=self.criteria_frame, anchor="nw")
        self.criteria_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        # Populate criteria widgets
        self.criterion_vars = []  # list of StringVar for each criterion
        self.criterion_widgets = []
        # Organize criteria by RA for grouping
        grouped = {}
        for item in self.rubric:
            grouped.setdefault(item["ra_id"], []).append(item)
        row_idx = 0
        for ra_id, items in grouped.items():
            # RA header
            ra_label = ttk.Label(
                self.criteria_frame,
                text=f"{ra_id} – {items[0]['competency']}",
                font=("TkDefaultFont", 10, "bold")
            )
            ra_label.grid(row=row_idx, column=0, columnspan=3, sticky="w", pady=(8 if row_idx else 0, 2))
            row_idx += 1
            for item in items:
                var = tk.StringVar(value="")
                self.criterion_vars.append(var)
                # Label for criterion
                crit_label = ttk.Label(self.criteria_frame, text=item["criterion"])
                crit_label.grid(row=row_idx, column=0, sticky="w", padx=(0, 5), pady=2)
                # Option menu for level selection
                level_menu = ttk.OptionMenu(
                    self.criteria_frame,
                    var,
                    "",
                    "DD",
                    "DS",
                    "DI",
                    "SD",
                    command=lambda *_: self.update_score()
                )
                level_menu.grid(row=row_idx, column=1, sticky="w", pady=2)
                # Weight label
                weight_lbl = ttk.Label(self.criteria_frame, text=f"Ponderación: {item['weight']:.2f}")
                weight_lbl.grid(row=row_idx, column=2, sticky="w", padx=(10, 0), pady=2)
                # Save metadata on the widget for lookup
                self.criterion_widgets.append({
                    "var": var,
                    "item": item
                })
                row_idx += 1

        # Separator and results
        sep = ttk.Separator(right_frame, orient="horizontal")
        sep.pack(fill=tk.X, pady=5)
        results_frame = ttk.Frame(right_frame)
        results_frame.pack(fill=tk.X)
        self.score_label = ttk.Label(results_frame, text="Puntaje: 0.00")
        self.score_label.pack(side=tk.LEFT)
        self.grade_label = ttk.Label(results_frame, text="Nota final: 0.0")
        self.grade_label.pack(side=tk.LEFT, padx=(10, 0))
        save_btn = ttk.Button(results_frame, text="Guardar evaluación", command=self.save_evaluation)
        save_btn.pack(side=tk.RIGHT)

    def _on_frame_configure(self, event):
        """Reset the scroll region to encompass the inner frame."""
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event):
        """Adjust the inner frame's width to fill the canvas."""
        canvas_width = event.width
        self.canvas.itemconfigure(self.canvas_frame, width=canvas_width)

    def on_student_select(self, event):
        """Called when a student is selected from the listbox."""
        selection = event.widget.curselection()
        if not selection:
            return
        index = selection[0]
        student = self.students[index]
        self.current_student_id = student["id"]
        # Clear all selections
        for entry in self.criterion_widgets:
            entry["var"].set("")
        # Load existing evaluation if present
        eval_path = os.path.join(self.evals_dir, f"{self.current_student_id}.json")
        if os.path.isfile(eval_path):
            with open(eval_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                # Map criterion name to selected level
                selections = {e["criterion"]: e["level"] for e in data.get("evaluations", [])}
                for entry in self.criterion_widgets:
                    crit = entry["item"]["criterion"]
                    if crit in selections:
                        entry["var"].set(selections[crit])
        # Recompute score with loaded data
        self.update_score()

    def update_score(self) -> None:
        """Recalculate and display the weighted score and final grade."""
        total_weight = sum(item["item"]["weight"] for item in self.criterion_widgets)
        weighted_sum = 0.0
        for entry in self.criterion_widgets:
            level_code = entry["var"].get()
            weight = entry["item"]["weight"]
            if level_code in self.level_values:
                value = self.level_values[level_code]
                weighted_sum += weight * value
        if total_weight == 0:
            ratio = 0
        else:
            ratio = weighted_sum / total_weight
        # Compute grade on 1–7 scale: grade = 1 + 6 * ratio
        grade = 1.0 + 6.0 * ratio
        # Update display
        self.score_label.config(text=f"Puntaje: {ratio:.2f}")
        self.grade_label.config(text=f"Nota final: {grade:.1f}")

    def save_evaluation(self) -> None:
        """Save current evaluation for selected student."""
        if self.current_student_id is None:
            messagebox.showwarning("Aviso", "Seleccione un estudiante antes de guardar.")
            return
        # Build evaluation record
        evaluations = []
        for entry in self.criterion_widgets:
            level = entry["var"].get()
            evaluations.append({
                "criterion": entry["item"]["criterion"],
                "level": level,
                "weight": entry["item"]["weight"]
            })
        # Compute final scores
        total_weight = sum(item["weight"] for item in evaluations)
        weighted_sum = sum(
            entry["weight"] * self.level_values.get(entry["level"], 0)
            for entry in evaluations
        )
        ratio = weighted_sum / total_weight if total_weight else 0.0
        grade = 1.0 + 6.0 * ratio
        eval_data = {
            "student_id": self.current_student_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "evaluations": evaluations,
            "weighted_score": ratio,
            "final_grade": grade
        }
        # Write to file
        eval_path = os.path.join(self.evals_dir, f"{self.current_student_id}.json")
        try:
            with open(eval_path, "w", encoding="utf-8") as f:
                json.dump(eval_data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo(
                "Guardado", f"Evaluación guardada para {self.current_student_id}"
            )
        except Exception as e:
            messagebox.showerror("Error", f"No se pudo guardar la evaluación: {e}")


def main():
    root = tk.Tk()
    # Determine the directory of this script to locate data files consistently
    script_dir = os.path.dirname(os.path.abspath(__file__))
    app = EvaluationApp(root, data_dir=script_dir)
    root.mainloop()


if __name__ == "__main__":
    main()