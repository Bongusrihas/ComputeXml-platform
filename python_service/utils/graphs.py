import numpy as np
import pandas as pd
from plotly import graph_objects as go
from plotly.subplots import make_subplots
from bokeh.plotting import figure, output_file, save
from bokeh.layouts import column as bokeh_column
from bokeh.models import ColumnDataSource
from plotly import express as px
from app.config import *
from .neccessity import make_artifact_path

def create_linear_graphs(original_name: str, plot_context: dict) -> dict:
    plotly_path = make_artifact_path("plotly", original_name, ".html")
    plotly_figure = make_subplots(rows=1, cols=2, subplot_titles=(plot_context["title"], "Residual Plot"))
    plotly_figure.add_trace(
        go.Scatter(
            x=plot_context["x_values"],
            y=plot_context["y_values"],
            mode="markers",
            name="Observed data",
            marker=dict(color="#2563eb", size=8, opacity=0.72),
        ),
        row=1,
        col=1,
    )
    plotly_figure.add_trace(
        go.Scatter(
            x=plot_context["line_x"],
            y=plot_context["line_y"],
            mode="lines",
            name="Regression line",
            line=dict(color="#dc2626", width=3),
        ),
        row=1,
        col=1,
    )
    plotly_figure.add_trace(
        go.Scatter(
            x=plot_context["residual_x"],
            y=plot_context["residual_y"],
            mode="markers",
            name="Residuals",
            marker=dict(color="#059669", size=8, opacity=0.72),
        ),
        row=1,
        col=2,
    )
    plotly_figure.add_trace(
        go.Scatter(
            x=[float(np.min(plot_context["residual_x"])), float(np.max(plot_context["residual_x"]))],
            y=[0, 0],
            mode="lines",
            name="Zero residual",
            line=dict(color="#94a3b8", dash="dash"),
        ),
        row=1,
        col=2,
    )
    plotly_figure.update_xaxes(title_text=plot_context["x_label"], row=1, col=1)
    plotly_figure.update_yaxes(title_text=plot_context["y_label"], row=1, col=1)
    plotly_figure.update_xaxes(title_text="Predicted / Feature", row=1, col=2)
    plotly_figure.update_yaxes(title_text="Residual", row=1, col=2)
    plotly_figure.update_layout(title="Linear Regression Graphs")
    plotly_figure.write_html(str(plotly_path), full_html=True)

    bokeh_path = make_artifact_path("bokeh", original_name, ".html")
    output_file(str(bokeh_path))
    main_figure = figure(title=plot_context["title"], width=980, height=360, x_axis_label=plot_context["x_label"], y_axis_label=plot_context["y_label"])
    main_figure.scatter(plot_context["x_values"], plot_context["y_values"], size=8, alpha=0.65, color="#2563eb")
    main_figure.line(plot_context["line_x"], plot_context["line_y"], line_width=3, color="#dc2626")

    residual_figure = figure(title="Residual Plot", width=980, height=320, x_axis_label="Predicted / Feature", y_axis_label="Residual")
    residual_figure.scatter(plot_context["residual_x"], plot_context["residual_y"], size=8, alpha=0.65, color="#059669")
    residual_figure.line(
        [float(np.min(plot_context["residual_x"])), float(np.max(plot_context["residual_x"]))],
        [0, 0],
        line_dash="dashed",
        color="#94a3b8",
    )
    save(bokeh_column(main_figure, residual_figure))

    return {
        "plotly": f"/static/artifacts/{plotly_path.name}",
        "bokeh": f"/static/artifacts/{bokeh_path.name}",
        "mode": "linear",
    }


def create_logistic_graphs(original_name: str, plot_context: dict) -> dict:
    plotly_path = make_artifact_path("plotly", original_name, ".html")
    plotly_figure = make_subplots(rows=1, cols=2, subplot_titles=(plot_context["title"], f"ROC Curve (AUC {plot_context['auc']:.3f})"))
    plotly_figure.add_trace(
        go.Scatter(
            x=plot_context["actual_x"],
            y=plot_context["actual_y"],
            mode="markers",
            name="Actual class",
            marker=dict(color="#2563eb", size=8, opacity=0.72),
        ),
        row=1,
        col=1,
    )
    plotly_figure.add_trace(
        go.Scatter(
            x=plot_context["curve_x"],
            y=plot_context["curve_y"],
            mode="lines",
            name="Predicted probability",
            line=dict(color="#dc2626", width=3),
        ),
        row=1,
        col=1,
    )
    plotly_figure.add_trace(
        go.Scatter(
            x=plot_context["fpr"],
            y=plot_context["tpr"],
            mode="lines",
            name="ROC",
            line=dict(color="#059669", width=3),
        ),
        row=1,
        col=2,
    )
    plotly_figure.add_trace(
        go.Scatter(
            x=[0, 1],
            y=[0, 1],
            mode="lines",
            name="Baseline",
            line=dict(color="#94a3b8", dash="dash"),
        ),
        row=1,
        col=2,
    )
    plotly_figure.update_xaxes(title_text=plot_context["x_label"], row=1, col=1)
    plotly_figure.update_yaxes(title_text="Probability / Class", row=1, col=1)
    plotly_figure.update_xaxes(title_text="False Positive Rate", row=1, col=2)
    plotly_figure.update_yaxes(title_text="True Positive Rate", row=1, col=2)
    plotly_figure.update_layout(title="Logistic Regression Graphs")
    plotly_figure.write_html(str(plotly_path), full_html=True)

    bokeh_path = make_artifact_path("bokeh", original_name, ".html")
    output_file(str(bokeh_path))

    probability_figure = figure(title=plot_context["title"], width=980, height=360, x_axis_label=plot_context["x_label"], y_axis_label="Probability / Class")
    probability_figure.scatter(plot_context["actual_x"], plot_context["actual_y"], size=8, alpha=0.65, color="#2563eb")
    probability_figure.line(plot_context["curve_x"], plot_context["curve_y"], line_width=3, color="#dc2626")

    roc_source = ColumnDataSource({"fpr": plot_context["fpr"], "tpr": plot_context["tpr"]})
    roc_figure = figure(
        title=f"ROC Curve (AUC {plot_context['auc']:.3f})",
        width=980,
        height=320,
        x_axis_label="False Positive Rate",
        y_axis_label="True Positive Rate",
        x_range=(0, 1),
        y_range=(0, 1),
    )
    roc_figure.line("fpr", "tpr", source=roc_source, line_width=3, color="#059669")
    roc_figure.line([0, 1], [0, 1], line_dash="dashed", color="#94a3b8")
    save(bokeh_column(probability_figure, roc_figure))

    return {
        "plotly": f"/static/artifacts/{plotly_path.name}",
        "bokeh": f"/static/artifacts/{bokeh_path.name}",
        "mode": "logistic",
    }


def create_categorical_graphs(frame: pd.DataFrame, original_name: str) -> dict:
    if frame.empty:
        return {"plotly": None, "bokeh": None, "mode": "none", "reason": "empty dataframe"}

    first_column = str(frame.columns[0])
    counts = frame[first_column].astype(str).fillna("NA").value_counts().head(25)
    if counts.empty:
        return {"plotly": None, "bokeh": None, "mode": "none", "reason": "empty categorical counts"}

    category_frame = pd.DataFrame({"category": counts.index.tolist(), "count": counts.values.tolist()})

    plotly_path = make_artifact_path("plotly", original_name, ".html")
    plotly_figure = px.bar(category_frame, x="category", y="count", title=f"Category Distribution: {first_column}")
    plotly_figure.write_html(str(plotly_path), full_html=True)

    bokeh_path = make_artifact_path("bokeh", original_name, ".html")
    output_file(str(bokeh_path))
    source = ColumnDataSource(category_frame)
    bokeh_figure = figure(
        x_range=category_frame["category"].tolist(),
        title=f"Category Distribution: {first_column}",
        width=900,
        height=380,
    )
    bokeh_figure.vbar(x="category", top="count", width=0.8, source=source)
    bokeh_figure.xaxis.major_label_orientation = 1.0
    save(bokeh_figure)

    return {
        "plotly": f"/static/artifacts/{plotly_path.name}",
        "bokeh": f"/static/artifacts/{bokeh_path.name}",
        "mode": "categorical",
    }