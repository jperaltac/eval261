"""
Aplicación de evaluación con Tkinter.

Mejoras principales respecto a la versión inicial:
- Vista de estudiantes tipo planilla con estado, progreso y nota final.
- Evaluación por pestañas de RA (agrupación por elemento de rúbrica).
- Selección por criterio con niveles DD/DS/DI/SD y detalle contextual.
- Advertencias claras cuando hay casillas sin completar.
- Panel de resumen para apoyar la gestión de evaluaciones.
"""

import datetime
import json
import os
import tkinter as tk
import unicodedata
from tkinter import messagebox, ttk


class EvaluationApp:
    """Main application class for student evaluation."""

    LEVEL_ORDER = ("DD", "DS", "DI", "SD")
    SECTION_ORDER = ("ESCRITO", "COMPETENCIAS GENERALES", "CÓDIGO COMPUTACIONAL")

    @staticmethod
    def _normalize_text(value: str) -> str:
        """Normaliza textos para evitar inconsistencias de acentos Unicode."""
        return unicodedata.normalize("NFC", value).strip()

    def _normalize_structure(self, value):
        """Normaliza strings dentro de listas/diccionarios de forma recursiva."""
        if isinstance(value, str):
            return self._normalize_text(value)
        if isinstance(value, list):
            return [self._normalize_structure(item) for item in value]
        if isinstance(value, dict):
            return {key: self._normalize_structure(item) for key, item in value.items()}
        return value

    def __init__(self, master: tk.Tk, data_dir: str = "."):
        self.master = master
        self.master.title("Evaluación de Estudiantes")
        self.master.geometry("1360x860")
        self.data_dir = data_dir

        rubric_path = os.path.join(data_dir, "rubric.json")
        students_path = os.path.join(data_dir, "students.json")
        if not os.path.isfile(rubric_path) or not os.path.isfile(students_path):
            messagebox.showerror(
                "Error", "No se encontraron los archivos rubric.json o students.json en " + data_dir
            )
            self.master.destroy()
            return

        with open(rubric_path, "r", encoding="utf-8") as f:
            self.rubric = self._normalize_structure(json.load(f))

        with open(students_path, "r", encoding="utf-8") as f:
            self.students = self._normalize_structure(json.load(f))

        self.evals_dir = os.path.join(data_dir, "evaluations")
        os.makedirs(self.evals_dir, exist_ok=True)

        # Valores de logro para cálculo ponderado
        self.level_values = {
            "DD": 1.0,   # Destacado
            "DS": 0.75,  # Satisfactorio
            "DI": 0.5,   # Insuficiente
            "SD": 0.25,  # Sin Dominio
        }

        self.current_student_id = None
        self.student_by_id = {s["id"]: s for s in self.students}
        self.evaluation_index = self._load_evaluation_index()

        # Estructura para widgets por criterio
        self.criterion_widgets = []

        # Mapa de labels de niveles para mejor legibilidad en UI
        self.level_labels = {
            "DD": "DD - Destacado",
            "DS": "DS - Satisfactorio",
            "DI": "DI - Insuficiente",
            "SD": "SD - Sin Dominio",
        }
        self.label_to_code = {v: k for k, v in self.level_labels.items()}
        self.bulk_criterion_var = tk.StringVar(value="")
        self.bulk_level_var = tk.StringVar(value="")

        self._build_ui()
        self._refresh_student_table()

    def _load_evaluation_index(self):
        """Carga evaluaciones existentes para poblar estado y progreso."""
        index = {}
        for student in self.students:
            student_id = student["id"]
            eval_path = os.path.join(self.evals_dir, f"{student_id}.json")
            if os.path.isfile(eval_path):
                try:
                    with open(eval_path, "r", encoding="utf-8") as f:
                        index[student_id] = self._normalize_structure(json.load(f))
                except (json.JSONDecodeError, OSError):
                    # Si hay un archivo corrupto, se ignora para no romper la interfaz
                    continue
        return index

    def _build_ui(self) -> None:
        """Construye layout principal."""
        self.master.columnconfigure(0, weight=1)
        self.master.rowconfigure(0, weight=1)

        container = ttk.Frame(self.master, padding=10)
        container.grid(row=0, column=0, sticky="nsew")
        container.columnconfigure(0, weight=0)
        container.columnconfigure(1, weight=1)
        container.rowconfigure(0, weight=1)

        self._build_left_panel(container)
        self._build_right_panel(container)

    def _build_left_panel(self, parent: ttk.Frame) -> None:
        """Panel izquierdo: gestión de estudiantes y estado general."""
        left = ttk.Frame(parent)
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        left.columnconfigure(0, weight=1)

        ttk.Label(left, text="Gestión de estudiantes", font=("TkDefaultFont", 11, "bold")).grid(
            row=0, column=0, sticky="w"
        )

        filter_row = ttk.Frame(left)
        filter_row.grid(row=1, column=0, sticky="ew", pady=(8, 6))
        ttk.Label(filter_row, text="Filtro:").pack(side=tk.LEFT)
        self.status_filter = tk.StringVar(value="Todos")
        filter_combo = ttk.Combobox(
            filter_row,
            width=14,
            textvariable=self.status_filter,
            values=["Todos", "Pendientes", "Completados"],
            state="readonly",
        )
        filter_combo.pack(side=tk.LEFT, padx=(6, 0))
        filter_combo.bind("<<ComboboxSelected>>", lambda *_: self._refresh_student_table())

        columns = ("student", "state", "progress", "grade")
        self.student_tree = ttk.Treeview(
            left,
            columns=columns,
            show="headings",
            height=28,
            selectmode="extended",
        )
        self.student_tree.heading("student", text="Estudiante")
        self.student_tree.heading("state", text="Estado")
        self.student_tree.heading("progress", text="Progreso")
        self.student_tree.heading("grade", text="Nota")
        self.student_tree.column("student", width=280, anchor="w")
        self.student_tree.column("state", width=95, anchor="center")
        self.student_tree.column("progress", width=90, anchor="center")
        self.student_tree.column("grade", width=65, anchor="center")
        self.student_tree.grid(row=2, column=0, sticky="nsew")
        self.student_tree.bind("<<TreeviewSelect>>", self.on_student_select)

        yscroll = ttk.Scrollbar(left, orient="vertical", command=self.student_tree.yview)
        self.student_tree.configure(yscrollcommand=yscroll.set)
        yscroll.grid(row=2, column=1, sticky="ns")

        stats_frame = ttk.LabelFrame(left, text="Resumen")
        stats_frame.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        self.summary_label = ttk.Label(stats_frame, text="Evaluados: 0 / 0")
        self.summary_label.pack(anchor="w", padx=8, pady=6)

        bulk_frame = ttk.LabelFrame(left, text="Aplicación masiva (seleccionados)")
        bulk_frame.grid(row=4, column=0, sticky="ew", pady=(8, 0))
        bulk_frame.columnconfigure(0, weight=1)

        criterion_values = [item["criterion"] for item in self.rubric]
        ttk.Label(bulk_frame, text="Criterio").grid(row=0, column=0, sticky="w", padx=8, pady=(8, 2))
        bulk_criterion_combo = ttk.Combobox(
            bulk_frame,
            textvariable=self.bulk_criterion_var,
            state="readonly",
            values=criterion_values,
        )
        bulk_criterion_combo.grid(row=1, column=0, sticky="ew", padx=8)

        ttk.Label(bulk_frame, text="Nivel").grid(row=2, column=0, sticky="w", padx=8, pady=(8, 2))
        bulk_level_combo = ttk.Combobox(
            bulk_frame,
            textvariable=self.bulk_level_var,
            state="readonly",
            values=[self.level_labels[c] for c in self.LEVEL_ORDER],
        )
        bulk_level_combo.grid(row=3, column=0, sticky="ew", padx=8)

        apply_bulk_btn = ttk.Button(
            bulk_frame, text="Aplicar a seleccionados", command=self.apply_bulk_level
        )
        apply_bulk_btn.grid(row=4, column=0, sticky="ew", padx=8, pady=8)

    def _build_right_panel(self, parent: ttk.Frame) -> None:
        """Panel derecho: rúbrica, detalle y resultados."""
        right = ttk.Frame(parent)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        # Encabezado del estudiante seleccionado
        self.selected_student_label = ttk.Label(
            right, text="Selecciona un estudiante", font=("TkDefaultFont", 11, "bold")
        )
        self.selected_student_label.grid(row=0, column=0, sticky="w", pady=(0, 8))

        body = ttk.Panedwindow(right, orient=tk.HORIZONTAL)
        body.grid(row=1, column=0, sticky="nsew")

        # Bloque principal con pestañas de rúbrica
        rubric_block = ttk.Frame(body)
        rubric_block.columnconfigure(0, weight=1)
        rubric_block.rowconfigure(0, weight=1)

        self.notebook = ttk.Notebook(rubric_block)
        self.notebook.grid(row=0, column=0, sticky="nsew")

        # Panel detalle del criterio seleccionado
        detail_block = ttk.LabelFrame(body, text="Detalle del criterio")
        detail_block.columnconfigure(0, weight=1)
        detail_block.rowconfigure(1, weight=1)
        self.detail_title = ttk.Label(detail_block, text="Selecciona un criterio para ver detalles")
        self.detail_title.grid(row=0, column=0, sticky="w", padx=8, pady=(8, 4))
        self.detail_text = tk.Text(detail_block, wrap="word", width=44, height=30)
        self.detail_text.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 8))
        self.detail_text.configure(state="disabled")

        body.add(rubric_block, weight=3)
        body.add(detail_block, weight=2)

        # Barra inferior de resumen
        footer = ttk.Frame(right)
        footer.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        footer.columnconfigure(1, weight=1)

        self.missing_label = ttk.Label(footer, text="Casillas pendientes: 0")
        self.missing_label.grid(row=0, column=0, sticky="w")

        score_block = ttk.Frame(footer)
        score_block.grid(row=0, column=1, sticky="e")
        self.score_label = ttk.Label(score_block, text="Puntaje: 0.00")
        self.score_label.pack(side=tk.LEFT)
        self.grade_label = ttk.Label(score_block, text="Nota final: 0.0")
        self.grade_label.pack(side=tk.LEFT, padx=(10, 12))

        save_btn = ttk.Button(score_block, text="Guardar evaluación", command=self.save_evaluation)
        save_btn.pack(side=tk.LEFT)

        self._build_rubric_tabs()

    @staticmethod
    def _axis_from_ra_id(ra_id: str) -> str:
        """Obtiene AX (ámbito) desde identificador de RA."""
        return ra_id.split("-", maxsplit=1)[0] if "-" in ra_id else ""

    def _section_for_item(self, item: dict) -> str:
        """Define sección principal visible en pestañas."""
        section = item.get("section") or item.get("competency")
        section = self._normalize_text(section or "")
        if section:
            return section
        return "SIN SECCIÓN"

    def _build_rubric_tabs(self) -> None:
        """Crea pestañas por sección y muestra RA/AX como referencia secundaria."""
        grouped = {}
        for item in self.rubric:
            section = self._section_for_item(item)
            grouped.setdefault(section, []).append(item)

        ordered_sections = [
            section for section in self.SECTION_ORDER if section in grouped
        ] + [section for section in grouped if section not in self.SECTION_ORDER]

        for section in ordered_sections:
            items = grouped[section]
            frame = ttk.Frame(self.notebook, padding=8)
            frame.columnconfigure(0, weight=3)
            frame.columnconfigure(1, weight=1)
            frame.columnconfigure(2, weight=3)

            self.notebook.add(frame, text=section)

            title = ttk.Label(frame, text=section, font=("TkDefaultFont", 10, "bold"))
            title.grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 4))

            ra_refs = []
            for item in items:
                ra_ref = f"{item['ra_id']} ({self._axis_from_ra_id(item['ra_id'])})"
                if ra_ref not in ra_refs:
                    ra_refs.append(ra_ref)
            ttk.Label(
                frame,
                text="RA asociados: " + ", ".join(ra_refs),
                wraplength=740,
                foreground="#444",
            ).grid(
                row=1, column=0, columnspan=3, sticky="w", pady=(0, 10)
            )

            for idx, item in enumerate(items, start=2):
                row_frame = ttk.LabelFrame(
                    frame,
                    text=f"{item['criterion']} · {item['ra_id']}",
                    padding=6,
                )
                row_frame.grid(row=idx, column=0, columnspan=3, sticky="ew", pady=(0, 6))
                row_frame.columnconfigure(1, weight=1)

                ttk.Label(row_frame, text=f"Ponderación: {item['weight']:.2f}").grid(
                    row=0, column=0, sticky="w"
                )

                var = tk.StringVar(value="")
                combo = ttk.Combobox(
                    row_frame,
                    textvariable=var,
                    state="readonly",
                    values=[self.level_labels[c] for c in self.LEVEL_ORDER],
                    width=28,
                )
                combo.grid(row=0, column=1, sticky="w", padx=(12, 6))
                combo.bind("<<ComboboxSelected>>", lambda *_: self.update_score())

                details_btn = ttk.Button(
                    row_frame,
                    text="Ver niveles",
                    command=lambda it=item, v=var: self.show_criterion_detail(it, v),
                )
                details_btn.grid(row=0, column=2, sticky="e")

                self.criterion_widgets.append(
                    {
                        "item": item,
                        "var": var,
                    }
                )

    def _compute_progress_for_student(self, student_id: str):
        """Retorna estado, progreso y nota para un estudiante."""
        total = len(self.rubric)
        data = self.evaluation_index.get(student_id)
        if not data:
            return "Pendiente", 0, 0.0

        done = 0
        for entry in data.get("evaluations", []):
            if entry.get("level") in self.level_values:
                done += 1

        grade = float(data.get("final_grade", 0.0))
        state = "Completo" if done == total and total else "En curso"
        return state, done, grade

    def _refresh_student_table(self) -> None:
        """Actualiza tabla de estudiantes según filtro y evaluaciones guardadas."""
        current_filter = self.status_filter.get()

        for item_id in self.student_tree.get_children():
            self.student_tree.delete(item_id)

        total = len(self.students)
        completed = 0

        for student in self.students:
            student_id = student["id"]
            state, done, grade = self._compute_progress_for_student(student_id)
            if state == "Completo":
                completed += 1

            if current_filter == "Completados" and state != "Completo":
                continue
            if current_filter == "Pendientes" and state == "Completo":
                continue

            progress_text = f"{done}/{len(self.rubric)}"
            grade_text = f"{grade:.1f}" if grade > 0 else "-"
            self.student_tree.insert(
                "",
                tk.END,
                iid=student_id,
                values=(student["name"], state, progress_text, grade_text),
            )

        self.summary_label.config(text=f"Evaluados completos: {completed} / {total}")

    def on_student_select(self, event=None):
        """Carga evaluación del estudiante seleccionado en la interfaz."""
        selected = self.student_tree.selection()
        if not selected:
            return

        if len(selected) > 1:
            self.selected_student_label.config(
                text=f"Selección múltiple: {len(selected)} estudiantes"
            )
        student_id = selected[0]
        self.current_student_id = student_id
        student_name = self.student_by_id[student_id]["name"]
        if len(selected) == 1:
            self.selected_student_label.config(text=f"Estudiante: {student_name}")

        # Limpia selección actual
        for entry in self.criterion_widgets:
            entry["var"].set("")

        # Carga evaluación existente si corresponde
        eval_path = os.path.join(self.evals_dir, f"{student_id}.json")
        if os.path.isfile(eval_path):
            try:
                with open(eval_path, "r", encoding="utf-8") as f:
                    data = self._normalize_structure(json.load(f))
                selections = {
                    self._normalize_text(e.get("criterion", "")): e.get("level")
                    for e in data.get("evaluations", [])
                }
                for entry in self.criterion_widgets:
                    criterion = self._normalize_text(entry["item"]["criterion"])
                    code = selections.get(criterion, "")
                    if code in self.level_labels:
                        entry["var"].set(self.level_labels[code])
            except (json.JSONDecodeError, OSError):
                messagebox.showwarning(
                    "Aviso",
                    f"No se pudo leer la evaluación previa de {student_name}. Se cargará en blanco.",
                )

        self.update_score()

    def _build_or_update_eval_data(self, student_id: str, updates: dict) -> dict:
        """Obtiene datos de evaluación y aplica cambios por criterio."""
        eval_path = os.path.join(self.evals_dir, f"{student_id}.json")
        existing_entries = {}

        if os.path.isfile(eval_path):
            try:
                with open(eval_path, "r", encoding="utf-8") as f:
                    data = self._normalize_structure(json.load(f))
                for entry in data.get("evaluations", []):
                    criterion = self._normalize_text(entry.get("criterion", ""))
                    existing_entries[criterion] = entry.get("level", "")
            except (json.JSONDecodeError, OSError):
                existing_entries = {}

        evaluations = []
        for item in self.rubric:
            criterion = item["criterion"]
            criterion_key = self._normalize_text(criterion)
            level = updates.get(criterion_key, existing_entries.get(criterion_key, ""))
            evaluations.append(
                {
                    "criterion": criterion,
                    "level": level,
                    "weight": item["weight"],
                }
            )

        total_weight = sum(item["weight"] for item in evaluations)
        weighted_sum = sum(
            item["weight"] * self.level_values.get(item["level"], 0) for item in evaluations
        )
        ratio = (weighted_sum / total_weight) if total_weight else 0.0
        grade = 1.0 + 6.0 * ratio

        return {
            "student_id": student_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "evaluations": evaluations,
            "weighted_score": ratio,
            "final_grade": grade,
        }

    def apply_bulk_level(self) -> None:
        """Aplica un nivel a un criterio para todos los estudiantes seleccionados."""
        selected = self.student_tree.selection()
        if not selected:
            messagebox.showwarning("Aviso", "Selecciona uno o más estudiantes en la tabla.")
            return

        criterion = self.bulk_criterion_var.get().strip()
        level_code = self._selected_code(self.bulk_level_var)
        if not criterion or level_code not in self.level_values:
            messagebox.showwarning(
                "Aviso", "Debes elegir criterio y nivel antes de aplicar en forma masiva."
            )
            return

        criterion_key = self._normalize_text(criterion)
        errors = []
        updated = 0

        for student_id in selected:
            eval_data = self._build_or_update_eval_data(student_id, {criterion_key: level_code})
            eval_path = os.path.join(self.evals_dir, f"{student_id}.json")
            try:
                with open(eval_path, "w", encoding="utf-8") as f:
                    json.dump(eval_data, f, ensure_ascii=False, indent=2)
                self.evaluation_index[student_id] = eval_data
                updated += 1
            except OSError as exc:
                errors.append(f"{student_id}: {exc}")

        self._refresh_student_table()
        if self.current_student_id and self.student_tree.exists(self.current_student_id):
            self.student_tree.selection_add(self.current_student_id)

        if errors:
            messagebox.showwarning(
                "Aplicación parcial",
                f"Se actualizaron {updated} estudiantes.\n"
                f"Fallos: {len(errors)}\n- "
                + "\n- ".join(errors[:5]),
            )
            return

        messagebox.showinfo(
            "Aplicación masiva",
            f"Se aplicó {self.level_labels[level_code]} en '{criterion}' para {updated} estudiantes.",
        )

    def _selected_code(self, var: tk.StringVar) -> str:
        """Normaliza valor de combobox a código de nivel."""
        value = var.get().strip()
        if value in self.level_labels:
            return value
        return self.label_to_code.get(value, "")

    def show_criterion_detail(self, item: dict, var: tk.StringVar) -> None:
        """Muestra descripción detallada de niveles para un criterio."""
        selected = self._selected_code(var)
        lines = [
            f"Sección: {self._section_for_item(item)}",
            f"AX: {self._axis_from_ra_id(item['ra_id'])}",
            f"RA: {item['ra_id']}",
            f"Criterio: {item['criterion']}",
            f"Descripción RA: {item.get('ra_description', '')}",
            f"Ponderación: {item['weight']:.2f}",
            "",
            "Niveles de logro:",
        ]
        for code in self.LEVEL_ORDER:
            prefix = "▶ " if code == selected else "  "
            desc = item["levels"].get(code, "").strip()
            lines.append(f"{prefix}{self.level_labels[code]}")
            lines.append(f"{desc}\n")

        self.detail_title.config(text=f"Detalle · {item['criterion']}")
        self.detail_text.configure(state="normal")
        self.detail_text.delete("1.0", tk.END)
        self.detail_text.insert("1.0", "\n".join(lines))
        self.detail_text.configure(state="disabled")

    def update_score(self) -> None:
        """Recalcula puntaje, nota y casillas faltantes."""
        total_weight = sum(entry["item"]["weight"] for entry in self.criterion_widgets)
        weighted_sum = 0.0
        missing = 0

        for entry in self.criterion_widgets:
            code = self._selected_code(entry["var"])
            weight = entry["item"]["weight"]
            if code in self.level_values:
                weighted_sum += weight * self.level_values[code]
            else:
                missing += 1

        ratio = (weighted_sum / total_weight) if total_weight else 0.0
        grade = 1.0 + 6.0 * ratio

        self.score_label.config(text=f"Puntaje: {ratio:.2f}")
        self.grade_label.config(text=f"Nota final: {grade:.1f}")
        self.missing_label.config(text=f"Casillas pendientes: {missing}")

    def save_evaluation(self) -> None:
        """Guarda evaluación actual, advirtiendo casillas vacías."""
        if self.current_student_id is None:
            messagebox.showwarning("Aviso", "Selecciona un estudiante antes de guardar.")
            return

        evaluations = []
        missing_criteria = []

        for entry in self.criterion_widgets:
            code = self._selected_code(entry["var"])
            criterion = entry["item"]["criterion"]
            if code not in self.level_values:
                missing_criteria.append(criterion)
            evaluations.append(
                {
                    "criterion": criterion,
                    "level": code,
                    "weight": entry["item"]["weight"],
                }
            )

        if missing_criteria:
            preview = "\n- " + "\n- ".join(missing_criteria[:6])
            if len(missing_criteria) > 6:
                preview += f"\n- ... y {len(missing_criteria) - 6} más"
            should_continue = messagebox.askyesno(
                "Casillas vacías",
                "Hay criterios sin seleccionar.\n"
                f"Faltan {len(missing_criteria)} casillas:{preview}\n\n"
                "¿Deseas guardar de todas formas?",
            )
            if not should_continue:
                return

        total_weight = sum(item["weight"] for item in evaluations)
        weighted_sum = sum(
            item["weight"] * self.level_values.get(item["level"], 0)
            for item in evaluations
        )
        ratio = (weighted_sum / total_weight) if total_weight else 0.0
        grade = 1.0 + 6.0 * ratio

        eval_data = {
            "student_id": self.current_student_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "evaluations": evaluations,
            "weighted_score": ratio,
            "final_grade": grade,
        }

        eval_path = os.path.join(self.evals_dir, f"{self.current_student_id}.json")
        try:
            with open(eval_path, "w", encoding="utf-8") as f:
                json.dump(eval_data, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            messagebox.showerror("Error", f"No se pudo guardar la evaluación: {exc}")
            return

        self.evaluation_index[self.current_student_id] = eval_data
        self._refresh_student_table()
        # Mantener fila seleccionada
        if self.student_tree.exists(self.current_student_id):
            self.student_tree.selection_set(self.current_student_id)
            self.student_tree.see(self.current_student_id)

        messagebox.showinfo("Guardado", f"Evaluación guardada para {self.current_student_id}")


def main():
    root = tk.Tk()
    script_dir = os.path.dirname(os.path.abspath(__file__))
    EvaluationApp(root, data_dir=script_dir)
    root.mainloop()


if __name__ == "__main__":
    main()
