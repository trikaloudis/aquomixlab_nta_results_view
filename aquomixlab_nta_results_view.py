import streamlit as st
import pandas as pd
import plotly.express as px
import io

def main():
    """
    Main function to run the Streamlit application.
    This app allows users to upload data and metadata Excel files to generate
    interactive boxplots for statistical analysis.
    """
    st.set_page_config(layout="wide", page_title="Aquomixlab - NTA results brief view")

    st.title("Aquomixlab - NTA results brief view")

    # --- Sidebar for File Uploads ---
    st.sidebar.title("File Upload")
    st.sidebar.header("1. Upload Your Files")

    # File uploader for the main data
    data_file = st.sidebar.file_uploader(
        "Upload Data File (Excel)",
        type=['xlsx'],
        help="Upload the main dataset. Expects 'id', 'Consensus annotation', 'Compound Class', and sample columns."
    )

    # File uploader for the metadata
    metadata_file = st.sidebar.file_uploader(
        "Upload Metadata File (Excel)",
        type=['xlsx'],
        help="Upload the metadata file. Expects a 'Sample' column and attribute columns."
    )

    # --- Add Aquomixlab Logo and Link to Sidebar ---
    st.sidebar.markdown("---")
    # FIX: The URL must be a string (in quotes) and point to the raw image file.
    st.sidebar.image("https://raw.githubusercontent.com/trikaloudis/aquomixlab_nta_results_view/main/Aquomixlab%20Logo%20v2.png", use_container_width=True)
    st.sidebar.markdown(
        "<div style='text-align: center;'><a href='https://www.aquomixlab.com/'>https://www.aquomixlab.com/</a></div>",
        unsafe_allow_html=True
    )


    # --- Main App Logic ---
    if data_file is not None and metadata_file is not None:
        try:
            # --- NEW: Read and display information from Sheet2 ---
            try:
                # Read the first 5 rows from the second sheet (index 1)
                info_df = pd.read_excel(data_file, sheet_name=1, header=None, nrows=5)
                if not info_df.empty:
                    with st.expander("Show Dataset Information", expanded=True):
                        # Iterate through the rows and display them
                        for index, row in info_df.iterrows():
                            # Check if both columns exist to prevent errors
                            if len(row) >= 2 and pd.notna(row[0]) and pd.notna(row[1]):
                                st.markdown(f"**{row[0]}:** {row[1]}")
                            elif pd.notna(row[0]):
                                st.markdown(f"**{row[0]}**")
            except Exception:
                # If Sheet2 doesn't exist or there's an error, just show a warning
                st.warning("Could not read dataset information from the second sheet of the data file.")


            # Load the main data from the first sheet (index 0)
            data_df = pd.read_excel(data_file, sheet_name=0)
            metadata_df = pd.read_excel(metadata_file)

            # --- Data Validation ---
            # Check for essential columns in the data file
            required_data_cols = ['id', 'Consensus annotation', 'Compound Class']
            if not all(col in data_df.columns for col in required_data_cols):
                st.error(f"Data file is missing one or more required columns: {required_data_cols}")
                return

            # Check for essential columns in the metadata file
            if 'Sample' not in metadata_df.columns:
                st.error("Metadata file is missing the required 'Sample' column.")
                return

            # --- Data Processing and UI for Selections in Main Screen ---
            st.header("Analysis Controls")
            col1, col2 = st.columns(2)

            # --- Column 1: Sample Selection ---
            with col1:
                st.subheader("1. Select Samples")
                # Extract sample columns from the data file (all columns from F onwards)
                sample_cols = data_df.columns[5:].tolist()
                selected_samples = st.multiselect(
                    "Choose samples to include:",
                    options=sample_cols,
                    default=sample_cols
                )

                if not selected_samples:
                    st.warning("Please select at least one sample.")
                    return

            # --- Control 3: Feature Filtering (at the bottom) ---
            st.subheader("3. Filter Features")
            # Get unique compound classes for filtering
            compound_classes = ['All'] + sorted(data_df['Compound Class'].unique().tolist())
            selected_class = st.selectbox(
                "Filter by Compound Class:",
                options=compound_classes
            )

            # Filter data based on selected compound class
            if selected_class != 'All':
                filtered_data_df = data_df[data_df['Compound Class'] == selected_class].copy()
            else:
                filtered_data_df = data_df.copy()

            if filtered_data_df.empty:
                st.warning(f"No features found for the compound class: '{selected_class}'")
                # We must stop the script here if no features are available.
                return
            
            # Generate feature options based on the filter
            filtered_data_df['display_name'] = filtered_data_df['id'].astype(str) + " - " + filtered_data_df['Consensus annotation'].astype(str)
            feature_options = filtered_data_df['display_name'].tolist()

            # --- Column 2: Feature Selection and Grouping ---
            with col2:
                st.subheader("2. Select Feature and Group")
                
                selected_feature_display_name = st.selectbox(
                    "Select a feature to create a boxplot:",
                    options=feature_options,
                )

                # Allow user to select a metadata attribute for grouping, including 'Sample'
                grouping_options = metadata_df.columns.tolist()
                if not grouping_options:
                    st.error("Metadata file must have at least one attribute column.")
                    return

                selected_group = st.selectbox(
                    "Group boxplot by:",
                    options=grouping_options
                )

            # Get the actual ID from the selected display name
            selected_feature_id = filtered_data_df[filtered_data_df['display_name'] == selected_feature_display_name]['id'].iloc[0]


            # --- Boxplot Generation ---
            if st.button("Generate Boxplot"):
                st.header(f"Boxplot for Feature: {selected_feature_id}")
                # Get the selected feature's data
                feature_data = filtered_data_df[filtered_data_df['id'] == selected_feature_id]
                compound_name = feature_data['Consensus annotation'].iloc[0]
                st.subheader(f"Compound: {compound_name}")

                # Prepare data for plotting
                plot_data = feature_data[selected_samples].T.reset_index()
                plot_data.columns = ['Sample', 'Value']

                # --- FIX: Only merge if the grouping column is not 'Sample' ---
                if selected_group != 'Sample':
                    # Merge with metadata to get grouping information
                    plot_data = pd.merge(plot_data, metadata_df[['Sample', selected_group]], on='Sample', how='left')

                    if plot_data[selected_group].isnull().any():
                        st.warning(f"Some samples are missing a value for the grouping attribute '{selected_group}'. These samples will be excluded from the plot.")
                        plot_data.dropna(subset=[selected_group], inplace=True)
                
                # If grouping by 'Sample', the plot_data is already correct.
                # We just need to rename the column for the plot to work correctly.
                else:
                    plot_data = plot_data.rename(columns={'Sample': selected_group})


                # --- Display Plot and Download Options ---
                if not plot_data.empty:
                    # Create the boxplot using Plotly
                    fig = px.box(
                        plot_data,
                        x=selected_group,
                        y='Value',
                        color=selected_group,
                        title=f"Distribution of {selected_feature_id} ({compound_name}) by {selected_group}",
                        labels={"Value": "Measurement", selected_group: selected_group},
                        points="all" # Show individual data points
                    )
                    fig.update_layout(
                        title_x=0.5,
                        xaxis_title=selected_group,
                        yaxis_title="Value",
                        legend_title=selected_group
                    )

                    st.plotly_chart(fig, use_container_width=True)

                    # --- Download Buttons with Kaleido check ---
                    st.subheader("Download Plot")
                    try:
                        # Use gap="small" to bring the columns closer together
                        dl_col1, dl_col2 = st.columns(spec=2, gap="small")

                        # PNG Download
                        png_buffer = io.BytesIO()
                        fig.write_image(png_buffer, format="png", width=1000, height=600, scale=2)
                        png_buffer.seek(0)
                        dl_col1.download_button(
                            label="Download as PNG",
                            data=png_buffer,
                            file_name=f"boxplot_{selected_feature_id}.png",
                            mime="image/png"
                        )

                        # SVG Download
                        svg_buffer = io.BytesIO()
                        fig.write_image(svg_buffer, format="svg", width=1000, height=600, scale=2)
                        svg_buffer.seek(0)
                        dl_col2.download_button(
                            label="Download as SVG",
                            data=svg_buffer,
                            file_name=f"boxplot_{selected_feature_id}.svg",
                            mime="image/svg+xml"
                        )
                    except ValueError as e:
                        if "kaleido" in str(e):
                            st.error(
                                "Image export requires the 'kaleido' package. Please install it by running:\n\n"
                                "`pip install --upgrade kaleido`\n\n"
                                "After installation, please refresh the page."
                            )
                        else:
                            st.error(f"An error occurred during image export: {e}")
                else:
                    st.error("Could not generate plot. The selected samples might not have corresponding metadata for grouping.")

        except Exception as e:
            st.error(f"An error occurred: {e}")
            st.warning("Please ensure your uploaded files are in the correct format and all required columns are present.")

    else:
        st.info("Awaiting upload of both data and metadata Excel files in the sidebar.")
        st.markdown("""
        ### How to Use This App:
        1.  **Upload Files**: Use the sidebar to upload your Data and Metadata Excel files.
        2.  **Use the Controls**: Once files are uploaded, use the controls on this main screen to configure your analysis.
        3.  **Generate Plot**: Click the "Generate Boxplot" button to view and download your plot.
        """)

if __name__ == "__main__":
    main()


