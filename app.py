# Cell 1: Install Dependencies and Prepare Environment

# Step 1: Install necessary and stable libraries
print("⏳ Installing required libraries (Gradio, OpenCV)...")
!pip install gradio opencv-python --upgrade -q
print("✅ Libraries installed successfully.")

# Step 2: Import all necessary modules
import gradio as gr
import cv2
import numpy as np

# Step 3: Define the core backend function for analysis
def run_visual_analysis(img1_rgb, img2_rgb, ratio_threshold, method_choice):
    """
    A single, robust function to handle feature matching. It selects the matcher
    based on the user's choice from the UI.
    """
    # --- Input Validation ---
    if img1_rgb is None or img2_rgb is None:
        raise gr.Error("Please upload two images to compare.")

    matcher_type = "FLANN" if "FLANN" in method_choice else "Brute-Force"

    # --- Feature Detection ---
    img1_gray = cv2.cvtColor(img1_rgb, cv2.COLOR_RGB2GRAY)
    img2_gray = cv2.cvtColor(img2_rgb, cv2.COLOR_RGB2GRAY)
    sift = cv2.SIFT_create()
    kp1, des1 = sift.detectAndCompute(img1_gray, None)
    kp2, des2 = sift.detectAndCompute(img2_gray, None)

    if des1 is None or des2 is None or len(kp1) < 2 or len(kp2) < 2:
        return None, "Analysis Failed: Could not find enough features in one or both images. They may be too blurry, too small, or lack distinct details."

    # --- Feature Matching ---
    if matcher_type == 'FLANN':
        index_params = dict(algorithm=1, trees=5)
        search_params = dict(checks=50)
        matcher = cv2.FlannBasedMatcher(index_params, search_params)
    else: # Brute-Force
        matcher = cv2.BFMatcher()

    matches = matcher.knnMatch(np.float32(des1), np.float32(des2), k=2)

    # --- Filter Matches using Lowe's Ratio Test ---
    good_matches = []
    # Ensure matches were found and have the correct format (k=2)
    if matches and len(matches[0]) == 2:
        for m, n in matches:
            if m.distance < ratio_threshold * n.distance:
                good_matches.append(m)
    
    if len(good_matches) < 4:
        return None, f"Found only {len(good_matches)} high-quality matches. This is too few for a reliable geometric analysis. Try increasing the 'Match Sensitivity' slider."

    # --- Geometric Verification using Homography ---
    src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
    
    M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    
    if M is None or mask is None:
        return None, f"Found {len(good_matches)} initial matches, but could not establish a consistent geometric relationship. The scenes may be too different."
        
    inlier_mask = mask.ravel().tolist()
    inlier_count = sum(inlier_mask)

    if inlier_count < 4:
         return None, f"Found {len(good_matches)} initial matches, but only {inlier_count} were geometrically consistent. The scenes might be too different or the sensitivity setting too low."
         
    # --- Visualization ---
    h1, w1 = img1_rgb.shape[:2]
    h2, w2 = img2_rgb.shape[:2]
    combined_img = np.zeros((max(h1, h2), w1 + w2, 3), dtype=np.uint8)
    combined_img[:h1, :w1, :] = img1_rgb
    combined_img[:h2, w1:w1 + w2, :] = img2_rgb
    
    # Draw only the inlier matches (geometrically verified)
    for i, match in enumerate(good_matches):
        if inlier_mask[i]:
            pt1 = tuple(map(int, kp1[match.queryIdx].pt))
            pt2_shifted = (int(kp2[match.trainIdx].pt[0] + w1), int(kp2[match.trainIdx].pt[1]))
            # Draw a green line for the match
            cv2.line(combined_img, pt1, pt2_shifted, (34, 139, 34), 1, cv2.LINE_AA)
            # Draw cyan circles on the keypoints
            cv2.circle(combined_img, pt1, 4, (0, 255, 255), -1)
            cv2.circle(combined_img, pt2_shifted, 4, (0, 255, 255), -1)

    # --- Generate Summary Report ---
    summary = (
        f"**✅ {matcher_type} Analysis Complete**\n\n"
        f"- **Total Features Found:** Image 1: `{len(kp1)}`, Image 2: `{len(kp2)}`\n"
        f"- **High-Quality Matches (Ratio Test):** `{len(good_matches)}`\n"
        f"- **Geometrically Consistent Matches (Inliers):** `{inlier_count}`\n\n"
        f"The visualization highlights **{inlier_count}** structural elements robustly identified in both images."
    )
    return combined_img, summary

# Step 4: Build the Gradio Interface
with gr.Blocks(theme=gr.themes.Soft(primary_hue="slate", secondary_hue="orange")) as demo:
    gr.Markdown(
        "# 🖼️ Visual Feature Comparator\n"
        "Upload two images to find and visualize matching features. This tool uses SIFT and geometric verification to robustly compare scenes."
    )
    
    with gr.Row(variant="panel"):
        # --- Column 1: Controls ---
        with gr.Column(scale=1, min_width=350):
            gr.Markdown("### ⚙️ Controls")
            
            # Set value=None to start with an empty upload box
            img1_input = gr.Image(type="numpy", label="Upload Image 1")
            img2_input = gr.Image(type="numpy", label="Upload Image 2")
            
            with gr.Accordion("Analysis Settings", open=True):
                method_selector = gr.Radio(
                    choices=['SIFT + FLANN (Fast, Recommended)', 'SIFT + Brute-Force (Classic, Slower)'],
                    value='SIFT + FLANN (Fast, Recommended)',
                    label="Analysis Method"
                )
                ratio_slider = gr.Slider(
                    minimum=0.4, maximum=0.95, value=0.75, step=0.01,
                    label="Match Sensitivity",
                    info="Lower = fewer, higher-quality matches. Higher = more, potentially incorrect matches."
                )
            
            run_button = gr.Button("🚀 Run Visual Analysis", variant="primary")

        # --- Column 2: Results ---
        with gr.Column(scale=3):
            gr.Markdown("### 📊 Results")
            result_summary = gr.Markdown("Analysis results will be displayed here.", elem_id="summary_text")
            result_image = gr.Image(label="Visual Comparison", interactive=False, show_download_button=True)

    # Step 5: Define the main action for the run button
    run_button.click(
        fn=run_visual_analysis,
        inputs=[img1_input, img2_input, ratio_slider, method_selector],
        outputs=[result_image, result_summary],
        api_name="visual_analysis",
        show_progress="full"
    )

# Step 6: Launch the App
print("🚀 Launching the Visual Feature Comparator...")
demo.launch(debug=True, share=True)
