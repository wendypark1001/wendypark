# Wendy Kyungrim Park - Portfolio Website

A modern, responsive portfolio website showcasing the professional experience, education, and qualifications of Wendy Kyungrim Park.

## Features

- ✨ Modern, clean design
- 📱 Fully responsive (mobile, tablet, desktop)
- 🎨 Smooth animations and transitions
- ⚡ Fast loading static site
- 🔍 SEO-friendly structure
- ♿ Accessible navigation

## Technologies Used

- HTML5
- CSS3 (with CSS Grid and Flexbox)
- JavaScript (vanilla JS, no dependencies)
- Google Fonts (Inter)

## Sections

1. **Hero/About** - Introduction and professional summary
2. **Experience** - Timeline of work experience
3. **Education** - Academic background
4. **Skills & Qualifications** - Skills, languages, certifications, and awards
5. **Contact** - Email and LinkedIn information

## Deployment on GitHub Pages

This website is ready to be deployed on GitHub Pages. Follow these steps:

### Option 1: Deploy via GitHub Repository

1. **Create a new repository** on GitHub (or use this existing one)
   - Repository name: `wendypark` or your preferred name
   - Make sure it's public (for free GitHub Pages hosting)

2. **Push the files to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Portfolio website"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   git push -u origin main
   ```

3. **Enable GitHub Pages**
   - Go to your repository on GitHub
   - Click on **Settings**
   - Scroll down to **Pages** in the left sidebar
   - Under **Source**, select `main` branch and `/ (root)` folder
   - Click **Save**
   - Your site will be available at: `https://YOUR_USERNAME.github.io/YOUR_REPO_NAME/`

### Option 2: Use a Custom Domain

If you want to use a custom domain (e.g., `wendypark.com`):

1. Follow steps 1-2 above
2. In GitHub Pages settings, add your custom domain
3. Configure your DNS records as instructed by GitHub
4. Add a `CNAME` file in the repository root with your domain name

## Local Development

To view the website locally:

1. Clone the repository:
   ```bash
   git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
   cd YOUR_REPO_NAME
   ```

2. Open `index.html` in your web browser, or use a local server:
   ```bash
   # Using Python 3
   python3 -m http.server 8000
   
   # Using Node.js (http-server)
   npx http-server
   
   # Using PHP
   php -S localhost:8000
   ```

3. Navigate to `http://localhost:8000` in your browser

## File Structure

```
wendypark/
├── index.html          # Main HTML file
├── styles.css          # Stylesheet
├── script.js           # JavaScript for interactivity
└── README.md          # This file
```

## Customization

To customize the website:

- **Colors**: Edit CSS variables in `styles.css` (`:root` section)
- **Content**: Update the HTML in `index.html`
- **Fonts**: Modify the Google Fonts link in `index.html`
- **Animations**: Adjust animation timings in `script.js` and `styles.css`

## Browser Support

- Chrome (latest)
- Firefox (latest)
- Safari (latest)
- Edge (latest)
- Mobile browsers (iOS Safari, Chrome Mobile)

## License

This project is open source and available for personal use.

---

**Contact Information:**
- Email: wendy.park2003@gmail.com
- LinkedIn: [www.linkedin.com/in/wendy-park-47b563267](https://www.linkedin.com/in/wendy-park-47b563267)

