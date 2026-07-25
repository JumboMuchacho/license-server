// ================================
// Sticky Navbar
// ================================

const navbar = document.getElementById("navbar");

window.addEventListener("scroll", () => {

    if (window.scrollY > 40)
        navbar.classList.add("scrolled");
    else
        navbar.classList.remove("scrolled");

});

// ================================
// Reveal Sections
// ================================

const observer = new IntersectionObserver((entries)=>{

    entries.forEach(entry=>{

        if(entry.isIntersecting){

            entry.target.classList.add("show");

        }

    });

},{
    threshold:.15
});

document.querySelectorAll("section").forEach(section=>{

    section.classList.add("hidden");

    observer.observe(section);

});

// ================================
// Smooth Navigation
// ================================

document.querySelectorAll('nav a').forEach(anchor=>{

    anchor.addEventListener("click",function(e){

        e.preventDefault();

        document.querySelector(this.getAttribute("href"))

            .scrollIntoView({

                behavior:"smooth"

            });

    });

});

// ================================
// Download Button
// ================================

document.querySelectorAll(".download-btn")

.addEventListener("click",()=>{

    window.location="/downloads/TapTap3.0.zip"

});

const modal = document.getElementById("imageModal");
const modalImg = document.getElementById("modalImage");
const closeBtn = document.querySelector(".close-modal");

document.querySelectorAll(".setup-lightbox").forEach(item => {

    item.addEventListener("click", function(e){

        e.preventDefault();

        modal.style.display = "flex";

        modalImg.src = this.href;

    });

});

closeBtn.onclick = () => {

    modal.style.display = "none";

};

modal.onclick = (e)=>{

    if(e.target===modal){

        modal.style.display="none";

    }

};

document.addEventListener("keydown",(e)=>{

    if(e.key==="Escape"){

        modal.style.display="none";

    }

});
