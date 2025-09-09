// Flash messages auto-hide after 3 seconds
document.addEventListener("DOMContentLoaded", () => {
  const flashes = document.querySelectorAll(".flash");
  flashes.forEach(flash => {
    setTimeout(() => {
      flash.style.display = "none";
    }, 3000);
  });

  // Vote buttons (optional, if you want AJAX voting)
  const voteForms = document.querySelectorAll(".vote-form");
  voteForms.forEach(form => {
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const formData = new FormData(form);
      const action = formData.get("action");
      const memeId = form.dataset.memeId;
      try {
        const res = await fetch(`/vote/${memeId}`, {
          method: "POST",
          body: formData
        });
        if (res.ok) location.reload();
      } catch (err) {
        console.error("Error voting:", err);
      }
    });
  });

  // Optional: Image preview before upload
  const fileInput = document.querySelector('input[type="file"]');
  const previewImg = document.querySelector("#preview-img");
  if (fileInput && previewImg) {
    fileInput.addEventListener("change", (e) => {
      const file = e.target.files[0];
      if (file) previewImg.src = URL.createObjectURL(file);
    });
  }
});
