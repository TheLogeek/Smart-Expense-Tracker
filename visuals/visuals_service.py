import matplotlib.pyplot as plt
import gc
import io
import os
import numpy as np
from PIL import Image, ImageFilter
from matplotlib.patches import Patch # Import Patch for custom legend

class VisualsService:
    def __init__(self):
        # Use a non-interactive backend for matplotlib (headless mode)
        plt.switch_backend('Agg')

    def generate_pie_chart(self, data: list, title: str, show_legend: bool = False, filename="pie_chart.png"):
        labels = [d["category"] for d in data]
        sizes = [d["amount"] for d in data]

        if not sizes:
            fig, ax = plt.subplots(figsize=(6, 6))
            ax.text(0.5, 0.5, "No data available", horizontalalignment='center', verticalalignment='center', transform=ax.transAxes, fontsize=14)
            ax.set_aspect('equal')
            img_byte_arr = io.BytesIO()
            plt.savefig(img_byte_arr, format='png')
            plt.close(fig)
            return img_byte_arr.getvalue()

        fig, ax = plt.subplots(figsize=(8, 8))
        
        # autopct for percentage and amount only
        def autopct_amount_formatter(pct, allvals):
            absolute = int(np.round(pct/100.*np.sum(allvals)))
            if pct < 5: 
                return ''
            return f"{pct:.1f}%\n(₦{absolute:,})"

        wedges, texts = ax.pie( # Removed autotexts from return to handle manually
            sizes, 
            startangle=90,
            wedgeprops={'linewidth': 1, 'edgecolor': 'white'} # Add some spacing between wedges
        )

        total = sum(sizes)
        for i, wedge in enumerate(wedges):
            if sizes[i] / total > 0.05: # Only label slices > 5%
                angle = (wedge.theta2 - wedge.theta1) / 2. + wedge.theta1
                
                # Position for category name (closer to center)
                r_name = wedge.r * 0.5 # Adjust as needed for placement
                x_name = r_name * np.cos(np.deg2rad(angle))
                y_name = r_name * np.sin(np.deg2rad(angle))
                ax.text(x_name, y_name, labels[i], ha='center', va='center', fontsize=9, color='black', fontweight='bold')

                # Position for percentage and amount (further out)
                r_pct_amt = wedge.r * 0.8 # Adjust as needed for placement
                x_pct_amt = r_pct_amt * np.cos(np.deg2rad(angle))
                y_pct_amt = r_pct_amt * np.sin(np.deg2rad(angle))
                pct_val = (sizes[i] / total) * 100
                abs_val = sizes[i]
                ax.text(x_pct_amt, y_pct_amt, f"{pct_val:.1f}%\n(₦{abs_val:,})", ha='center', va='center', fontsize=8, color='w', fontweight='bold') # White color for percentage

        ax.set_title(title)
        ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.

        if show_legend:
            total = sum(sizes)
            legend_handles = []
            legend_labels = []
            for i, (label, size) in enumerate(zip(labels, sizes)):
                percentage = (size / total) * 100 if total > 0 else 0
                # Use a Patch for the color, then text for label and value
                legend_handles.append(Patch(facecolor=wedges[i].get_facecolor()))
                legend_labels.append(f"{label}\n({percentage:.1f}%) ₦{size:,.2f}")
            
            # Place legend outside the plot area
            ax.legend(legend_handles, legend_labels, title="Categories", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1),
                      fontsize=10, title_fontsize=12, frameon=True, fancybox=True, shadow=True, borderpad=1, labelspacing=1)

        img_byte_arr = io.BytesIO()
        plt.savefig(img_byte_arr, format='png', bbox_inches='tight')
        plt.close(fig) # Close the figure to free up memory
        gc.collect()
        return img_byte_arr.getvalue()

    def generate_donut_chart(self, data: list, title: str, show_legend: bool = False, filename="donut_chart.png"):
        labels = [d["category"] for d in data]
        sizes = [d["amount"] for d in data]

        if not sizes:
            fig, ax = plt.subplots(figsize=(6, 6))
            ax.text(0.5, 0.5, "No data available", horizontalalignment='center', verticalalignment='center', transform=ax.transAxes, fontsize=14)
            ax.set_aspect('equal')
            img_byte_arr = io.BytesIO()
            plt.savefig(img_byte_arr, format='png')
            plt.close(fig)
            gc.collect()
            return img_byte_arr.getvalue()

        fig, ax = plt.subplots(figsize=(8, 8))
        
        # autopct for percentage and amount only
        def autopct_amount_formatter(pct, allvals):
            absolute = int(np.round(pct/100.*np.sum(allvals)))
            if pct < 5: 
                return ''
            return f"{pct:.1f}%\n(₦{absolute:,})"

        wedges, texts = ax.pie( # Removed autotexts from return to handle manually
            sizes, 
            startangle=90,
            wedgeprops={'linewidth': 1, 'edgecolor': 'white'}
        )

        # Draw a circle at the center to make it a donut chart
        centre_circle = plt.Circle((0,0), 0.70, fc='white')
        fig.gca().add_artist(centre_circle)

        total = sum(sizes)
        for i, wedge in enumerate(wedges):
            if sizes[i] / total > 0.05: # Only label slices > 5%
                angle = (wedge.theta2 - wedge.theta1) / 2. + wedge.theta1
                
                # Position for category name (closer to center, outside the donut hole)
                r_name = wedge.r * 0.55 # Adjust as needed
                x_name = r_name * np.cos(np.deg2rad(angle))
                y_name = r_name * np.sin(np.deg2rad(angle))
                ax.text(x_name, y_name, labels[i], ha='center', va='center', fontsize=9, color='black', fontweight='bold')

                # Position for percentage and amount (further out)
                r_pct_amt = wedge.r * 0.85 # Adjust as needed
                x_pct_amt = r_pct_amt * np.cos(np.deg2rad(angle))
                y_pct_amt = r_pct_amt * np.sin(np.deg2rad(angle))
                pct_val = (sizes[i] / total) * 100
                abs_val = sizes[i]
                ax.text(x_pct_amt, y_pct_amt, f"{pct_val:.1f}%\n(₦{abs_val:,})", ha='center', va='center', fontsize=8, color='w', fontweight='bold') # White color for percentage

        ax.set_title(title)
        ax.axis('equal')  # Equal aspect ratio ensures that pie is drawn as a circle.

        if show_legend:
            total = sum(sizes)
            legend_handles = []
            legend_labels = []
            for i, (label, size) in enumerate(zip(labels, sizes)):
                percentage = (size / total) * 100 if total > 0 else 0
                legend_handles.append(Patch(facecolor=wedges[i].get_facecolor()))
                legend_labels.append(f"{label}\n({percentage:.1f}%) ₦{size:,.2f}")
            
            ax.legend(legend_handles, legend_labels, title="Categories", loc="center left", bbox_to_anchor=(1, 0, 0.5, 1),
                      fontsize=10, title_fontsize=12, frameon=True, fancybox=True, shadow=True, borderpad=1, labelspacing=1)

        img_byte_arr = io.BytesIO()
        plt.savefig(img_byte_arr, format='png', bbox_inches='tight')
        plt.close(fig) # Close the figure to free up memory
        return img_byte_arr.getvalue()

    def generate_bar_chart(self, data: list, title: str, overall_budget_amount: float = None, total_expenses_for_period: float = None, filename="bar_chart.png"):
        # Sort data by amount in descending order and take top 5
        data_sorted = sorted(data, key=lambda x: x['amount'], reverse=True)[:5]
        
        categories = [d["category"] for d in data_sorted]
        amounts = [d["amount"] for d in data_sorted]

        if not amounts:
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.text(0.5, 0.5, "No data available", horizontalalignment='center', verticalalignment='center', transform=ax.transAxes, fontsize=14)
            img_byte_arr = io.BytesIO()
            plt.savefig(img_byte_arr, format='png')
            plt.close(fig)
            return img_byte_arr.getvalue()

        fig, ax = plt.subplots(figsize=(10, 6))
        x_pos = np.arange(len(categories))
        ax.bar(x_pos, amounts, align='center') # Changed to vertical bar chart
        ax.set_xticks(x_pos)
        ax.set_xticklabels(categories, rotation=45, ha='right') # Rotate labels for better readability
        ax.set_ylabel('Amount (₦)') # Changed to ylabel
        ax.set_title(title)

        if overall_budget_amount is not None and overall_budget_amount > 0:
            line_color = 'green'
            if total_expenses_for_period is not None and total_expenses_for_period > overall_budget_amount:
                line_color = 'red'
            ax.axhline(y=overall_budget_amount, color=line_color, linestyle='--', linewidth=2, label=f'Budget: ₦{overall_budget_amount:,.2f}')
            ax.legend()

        plt.tight_layout()
        img_byte_arr = io.BytesIO()
        plt.savefig(img_byte_arr, format='png', bbox_inches='tight')
        plt.close(fig)
        gc.collect()
        return img_byte_arr.getvalue()
    
    def blur_image(self, image_bytes: bytes, radius: int = 10) -> bytes:
        img = Image.open(io.BytesIO(image_bytes))
        blurred_img = img.filter(ImageFilter.GaussianBlur(radius))
        blurred_img_byte_arr = io.BytesIO()
        blurred_img.save(blurred_img_byte_arr, format='PNG')
        return blurred_img_byte_arr.getvalue()