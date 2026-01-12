"""
Helper functions to prepare lab data for chart visualization and current value display.
"""

from typing import Dict, List, Any
from datetime import datetime


def prepare_chart_data(biomarker_data: Dict) -> Dict:
    """
    Prepare data for charting libraries (e.g., Chart.js, Recharts, Plotly).

    Args:
        biomarker_data: Single biomarker data with current and trend fields

    Returns:
        Chart-ready data with labels, values, and metadata
    """
    trend = biomarker_data.get("trend", [])

    if not trend:
        return {
            "labels": [],
            "values": [],
            "statuses": [],
            "has_data": False
        }

    # Sort by date
    sorted_trend = sorted(trend, key=lambda x: x.get("date", ""))

    # Extract data for chart
    labels = [item.get("date") for item in sorted_trend]
    values = [item.get("value") for item in sorted_trend]
    statuses = [item.get("status") for item in sorted_trend]

    # Determine color coding based on status
    colors = []
    for status in statuses:
        if status == "High":
            colors.append("#ef4444")  # Red
        elif status == "Low":
            colors.append("#f59e0b")  # Orange
        elif status == "Critical":
            colors.append("#dc2626")  # Dark red
        else:  # Normal
            colors.append("#10b981")  # Green

    return {
        "labels": labels,
        "values": values,
        "statuses": statuses,
        "colors": colors,
        "has_data": True,
        "data_points": len(values)
    }


def prepare_current_value_display(biomarker_data: Dict) -> Dict:
    """
    Prepare current value data for UI display.

    Args:
        biomarker_data: Single biomarker data

    Returns:
        Display-ready current value information
    """
    current = biomarker_data.get("current", {})

    value = current.get("value")
    unit = current.get("unit")
    date = current.get("date")
    status = current.get("status")
    reference_range = current.get("reference_range")

    # Determine if value is available
    has_value = value not in [None, "NA", ""]

    # Format display value
    if has_value:
        try:
            # Try to format as number with appropriate precision
            numeric_value = float(value)
            if numeric_value >= 100:
                display_value = f"{numeric_value:.0f}"
            elif numeric_value >= 10:
                display_value = f"{numeric_value:.1f}"
            else:
                display_value = f"{numeric_value:.2f}"
        except (ValueError, TypeError):
            display_value = str(value)
    else:
        display_value = "N/A"

    # Add unit if available
    if has_value and unit and unit not in [None, "NA", ""]:
        display_value = f"{display_value} {unit}"

    # Format date
    formatted_date = format_date(date) if date and date != "NA" else "N/A"

    # Determine status color and icon
    status_config = get_status_config(status)

    return {
        "value": display_value,
        "raw_value": value,
        "unit": unit if unit and unit != "NA" else None,
        "date": formatted_date,
        "raw_date": date,
        "status": status if status and status != "NA" else "Unknown",
        "status_color": status_config["color"],
        "status_icon": status_config["icon"],
        "reference_range": reference_range if reference_range and reference_range != "NA" else None,
        "has_value": has_value,
        "is_abnormal": status in ["High", "Low", "Critical"]
    }


def prepare_panel_for_display(panel_data: Dict, panel_name: str) -> Dict:
    """
    Prepare entire panel (tumor markers, CBC, metabolic) for display.

    Args:
        panel_data: Panel dictionary with all biomarkers
        panel_name: Name of the panel

    Returns:
        Display-ready panel data with current values and chart data
    """
    display_data = {
        "panel_name": panel_name,
        "biomarkers": []
    }

    for biomarker_name, biomarker_data in panel_data.items():
        biomarker_display = {
            "name": biomarker_name,
            "display_name": format_biomarker_name(biomarker_name),
            "current": prepare_current_value_display(biomarker_data),
            "chart": prepare_chart_data(biomarker_data),
            "trend_direction": biomarker_data.get("trend_direction"),
            "has_data": biomarker_data.get("has_data", False)
        }

        display_data["biomarkers"].append(biomarker_display)

    return display_data


def prepare_all_panels_for_display(processed_lab_data: Dict) -> Dict:
    """
    Prepare all panels for UI display.

    Args:
        processed_lab_data: Output from process_lab_data_for_ui

    Returns:
        Complete UI display data
    """
    return {
        "panels": [
            prepare_panel_for_display(
                processed_lab_data.get("tumor_markers", {}),
                "Tumor Markers"
            ),
            prepare_panel_for_display(
                processed_lab_data.get("complete_blood_count", {}),
                "Complete Blood Count"
            ),
            prepare_panel_for_display(
                processed_lab_data.get("metabolic_panel", {}),
                "Metabolic Panel"
            )
        ],
        "clinical_interpretation": processed_lab_data.get("clinical_interpretation", []),
        "summary": processed_lab_data.get("summary", {})
    }


# Helper functions

def format_date(date_str: str) -> str:
    """Format date string to readable format."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        return date_obj.strftime("%b %d, %Y")
    except (ValueError, TypeError):
        return date_str


def format_biomarker_name(name: str) -> str:
    """Format biomarker name for display."""
    # Special cases
    name_mapping = {
        "CEA": "CEA (Carcinoembryonic Antigen)",
        "NSE": "NSE (Neuron-Specific Enolase)",
        "proGRP": "ProGRP (Pro-Gastrin-Releasing Peptide)",
        "CYFRA_21_1": "CYFRA 21-1",
        "WBC": "WBC (White Blood Cells)",
        "ANC": "ANC (Absolute Neutrophil Count)",
        "ALT": "ALT (Alanine Aminotransferase)",
        "AST": "AST (Aspartate Aminotransferase)"
    }

    return name_mapping.get(name, name)


def get_status_config(status: str) -> Dict:
    """Get color and icon configuration for status."""
    status_configs = {
        "Normal": {
            "color": "#10b981",  # Green
            "icon": "check-circle"
        },
        "High": {
            "color": "#ef4444",  # Red
            "icon": "arrow-up-circle"
        },
        "Low": {
            "color": "#f59e0b",  # Orange
            "icon": "arrow-down-circle"
        },
        "Critical": {
            "color": "#dc2626",  # Dark red
            "icon": "exclamation-circle"
        },
        "Unknown": {
            "color": "#6b7280",  # Gray
            "icon": "question-mark-circle"
        }
    }

    return status_configs.get(status, status_configs["Unknown"])


# Example usage for specific chart libraries

def prepare_for_chartjs(biomarker_data: Dict, biomarker_name: str) -> Dict:
    """
    Prepare data in Chart.js format.

    Args:
        biomarker_data: Single biomarker data
        biomarker_name: Name of the biomarker

    Returns:
        Chart.js configuration object
    """
    chart_data = prepare_chart_data(biomarker_data)

    if not chart_data["has_data"]:
        return None

    return {
        "type": "line",
        "data": {
            "labels": chart_data["labels"],
            "datasets": [{
                "label": biomarker_name,
                "data": chart_data["values"],
                "borderColor": "#3b82f6",
                "backgroundColor": "rgba(59, 130, 246, 0.1)",
                "pointBackgroundColor": chart_data["colors"],
                "pointBorderColor": chart_data["colors"],
                "pointRadius": 6,
                "tension": 0.4
            }]
        },
        "options": {
            "responsive": True,
            "plugins": {
                "legend": {
                    "display": True
                },
                "tooltip": {
                    "callbacks": {
                        "afterLabel": lambda context: f"Status: {chart_data['statuses'][context['dataIndex']]}"
                    }
                }
            },
            "scales": {
                "y": {
                    "beginAtZero": False
                }
            }
        }
    }


def prepare_for_recharts(biomarker_data: Dict) -> List[Dict]:
    """
    Prepare data in Recharts format.

    Args:
        biomarker_data: Single biomarker data

    Returns:
        Array of data objects for Recharts
    """
    chart_data = prepare_chart_data(biomarker_data)

    if not chart_data["has_data"]:
        return []

    return [
        {
            "date": label,
            "value": value,
            "status": status,
            "color": color
        }
        for label, value, status, color in zip(
            chart_data["labels"],
            chart_data["values"],
            chart_data["statuses"],
            chart_data["colors"]
        )
    ]


def prepare_for_plotly(biomarker_data: Dict, biomarker_name: str) -> Dict:
    """
    Prepare data in Plotly format.

    Args:
        biomarker_data: Single biomarker data
        biomarker_name: Name of the biomarker

    Returns:
        Plotly figure configuration
    """
    chart_data = prepare_chart_data(biomarker_data)

    if not chart_data["has_data"]:
        return None

    return {
        "data": [{
            "x": chart_data["labels"],
            "y": chart_data["values"],
            "type": "scatter",
            "mode": "lines+markers",
            "name": biomarker_name,
            "marker": {
                "size": 10,
                "color": chart_data["colors"]
            },
            "line": {
                "color": "#3b82f6",
                "width": 2
            },
            "text": chart_data["statuses"],
            "hovertemplate": "%{x}<br>Value: %{y}<br>Status: %{text}<extra></extra>"
        }],
        "layout": {
            "title": f"{biomarker_name} Trend",
            "xaxis": {"title": "Date"},
            "yaxis": {"title": "Value"},
            "hovermode": "closest"
        }
    }
