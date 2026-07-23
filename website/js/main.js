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

document.getElementById("downloadButton")

.addEventListener("click",()=>{

    window.location="/downloads/TapTap.crx";

});
