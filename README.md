# SmartRoute: AI-Powered Campus HelpDesk System

![Python](https://img.shields.io/badge/Python-3.13-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0.0-black.svg)
![SQLite](https://img.shields.io/badge/SQLite-Database-blue.svg)
![Scikit-Learn](https://img.shields.io/badge/Machine%20Learning-Scikit--Learn-orange.svg)
![Socket.IO](https://img.shields.io/badge/WebSockets-Flask--SocketIO-green.svg)
![Chart.js](https://img.shields.io/badge/Analytics-Chart.js-red.svg)

SmartRoute is an enterprise-grade, intelligent Campus HelpDesk SaaS platform. It leverages **Machine Learning (NLP)** and **Sentiment Analysis** to automatically route student complaints to the correct college department while analyzing their emotional state to prioritize urgent issues.

Coupled with a **Real-Time WebSocket** chat architecture and a robust **Analytics Dashboard**, SmartRoute represents a modern approach to automated workflow management.

## 🚀 Key Features

### 🧠 1. Artificial Intelligence Engine
- **Automated Routing:** Uses an NLP pipeline (Scikit-Learn + TF-IDF) to analyze the textual content of a complaint and instantly route it to the correct department (IT, Maintenance, HR, Finance).
- **Sentiment Escalation:** Utilizes `vaderSentiment` to analyze the frustration level of the user. "Angry" or "Frustrated" complaints automatically bypass standard queues and are elevated to **High Priority**.
- **Confidence Scoring:** The model exposes probability distributions, allowing administrators to see the AI's confidence percentage for every routing decision.

### ⏱️ 2. Dynamic SLA (Service Level Agreement) System
- Computes strict resolution deadlines dynamically based on department configurations and priority overrides.
- Visual badges automatically warn staff when a ticket is `Near Deadline` or `Overdue`.

### 💬 3. Real-Time Chat & Notifications
- **Live Communication:** Powered by `Flask-SocketIO`, students and staff can converse in an isolated, secure real-time messaging room attached specifically to their ticket.
- **Global Event Broadcasting:** Resolving a ticket or escalating its priority triggers an instant Bootstrap Toast notification and updates the system bell icon across all active sessions.

### 📊 4. Enterprise Analytics Dashboard
- Features a premium Glassmorphism UI rendering asynchronous `Chart.js` visualizations.
- **KPI Monitoring:** Real-time metrics tracking Total, Pending, Resolved, and SLA Breached complaints.
- **Data Export:** Clean `window.print()` CSS logic for automated PDF report generation, alongside Python `io.StringIO` optimized CSV exporting.

### 🔐 5. Security Architecture
- Role-Based Access Control (Admin, Department, Student).
- Implicit WebSocket session validation to prevent unauthorized room joining.
- File upload sanitization (UUID renaming, strict MIME type enforcement).

---

## 🛠️ Technology Stack

| Category | Technology |
|---|---|
| **Backend Framework** | Python 3, Flask |
| **Database & ORM** | SQLite, SQLAlchemy, Flask-Migrate |
| **Machine Learning** | Scikit-Learn, Pandas, vaderSentiment |
| **Real-Time Engine** | WebSockets, Flask-SocketIO, Eventlet |
| **Frontend Styling** | HTML5, Bootstrap 5, Vanilla CSS (Glassmorphism) |
| **Data Visualization** | Chart.js |

---

## 📦 Installation & Setup

1. **Clone the Repository:**
```bash
git clone https://github.com/VaishnaviRaut2004/face-recognition-based-attendance-system-master.git
cd Campus-HelpDesk
```

2. **Install Dependencies:**
```bash
pip install -r requirements.txt
```

3. **Initialize Database:**
```bash
flask db upgrade
```

4. **Run the Application:**
```bash
python app.py
```
*The application will boot on `http://127.0.0.1:5000`.*

---

## 🏗️ Architecture & Database Optimization
- **B-Tree Indexing:** High query traffic columns (`status`, `department_id`, `priority`, `sentiment`) are indexed to guarantee `O(log n)` traversal speeds.
- **N+1 Query Elimination:** SQLAlchemy's `joinedload()` is used heavily across the dashboard endpoints to eagerly fetch relational data, ensuring constant query volume regardless of database size.

## 🔮 Future Scalability
- **PostgreSQL Migration:** Ready for transition via the existing `Flask-Migrate` schema.
- **Redis Integration:** Prepared for SocketIO multi-node horizontal scaling.
- **Cloud Storage:** Architecture allows easy hook-in to AWS S3 for complaint attachments.

---
*Developed as a modern, high-performance portfolio application showcasing Full-Stack Engineering, Applied Machine Learning, and Real-Time Systems.*
