document.addEventListener('DOMContentLoaded', function() {
    // Chart configurations
    Chart.defaults.color = 'rgba(255, 255, 255, 0.7)';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.1)';
    
    // When printing, we need charts to render solid colors
    window.addEventListener('beforeprint', () => {
        for (let id in Chart.instances) {
            Chart.instances[id].options.plugins.legend.labels.color = 'black';
            Chart.instances[id].options.scales.x.ticks.color = 'black';
            Chart.instances[id].options.scales.y.ticks.color = 'black';
            Chart.instances[id].update();
        }
    });

    window.addEventListener('afterprint', () => {
        for (let id in Chart.instances) {
            Chart.instances[id].options.plugins.legend.labels.color = 'rgba(255, 255, 255, 0.7)';
            Chart.instances[id].options.scales.x.ticks.color = 'rgba(255, 255, 255, 0.7)';
            Chart.instances[id].options.scales.y.ticks.color = 'rgba(255, 255, 255, 0.7)';
            Chart.instances[id].update();
        }
    });

    let sentimentChart = null;
    let deptChart = null;

    function initCharts(data) {
        // Prepare Sentiment Data
        const ctxSentiment = document.getElementById('sentimentChart').getContext('2d');
        sentimentChart = new Chart(ctxSentiment, {
            type: 'doughnut',
            data: {
                labels: ['Angry', 'Frustrated', 'Neutral', 'Positive'],
                datasets: [{
                    data: [
                        data.sentiments.Angry || 0,
                        data.sentiments.Frustrated || 0,
                        data.sentiments.Neutral || 0,
                        data.sentiments.Positive || 0
                    ],
                    backgroundColor: [
                        'rgba(220, 53, 69, 0.8)',   // Danger/Red
                        'rgba(253, 126, 20, 0.8)',  // Warning/Orange
                        'rgba(108, 117, 125, 0.8)', // Secondary/Gray
                        'rgba(25, 135, 84, 0.8)'    // Success/Green
                    ],
                    borderWidth: 1,
                    borderColor: '#1e1e28'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom' }
                }
            }
        });

        // Prepare Department Data
        const ctxDept = document.getElementById('deptChart').getContext('2d');
        const deptLabels = Object.keys(data.departments);
        const deptValues = Object.values(data.departments);
        
        deptChart = new Chart(ctxDept, {
            type: 'bar',
            data: {
                labels: deptLabels,
                datasets: [{
                    label: 'Complaints',
                    data: deptValues,
                    backgroundColor: 'rgba(13, 110, 253, 0.6)', // Primary/Blue
                    borderColor: 'rgba(13, 110, 253, 1)',
                    borderWidth: 1,
                    borderRadius: 5
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, ticks: { stepSize: 1 } }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    function updateKPIs(kpis) {
        // Animation helper
        const animateValue = (id, start, end, duration) => {
            if (start === end) {
                document.getElementById(id).innerHTML = end;
                return;
            }
            const obj = document.getElementById(id);
            let startTimestamp = null;
            const step = (timestamp) => {
                if (!startTimestamp) startTimestamp = timestamp;
                const progress = Math.min((timestamp - startTimestamp) / duration, 1);
                obj.innerHTML = Math.floor(progress * (end - start) + start);
                if (progress < 1) {
                    window.requestAnimationFrame(step);
                } else {
                    obj.innerHTML = end;
                }
            };
            window.requestAnimationFrame(step);
        };
        
        const curTotal = parseInt(document.getElementById('kpiTotal').innerText) || 0;
        const curPending = parseInt(document.getElementById('kpiPending').innerText) || 0;
        const curResolved = parseInt(document.getElementById('kpiResolved').innerText) || 0;
        const curOverdue = parseInt(document.getElementById('kpiOverdue').innerText) || 0;

        animateValue('kpiTotal', curTotal, kpis.total, 800);
        animateValue('kpiPending', curPending, kpis.pending, 800);
        animateValue('kpiResolved', curResolved, kpis.resolved, 800);
        animateValue('kpiOverdue', curOverdue, kpis.overdue, 800);
    }

    function fetchAnalytics() {
        fetch('/api/analytics/data')
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    console.error("Auth error:", data.error);
                    return;
                }
                
                // Update KPIs
                updateKPIs(data.kpis);

                // Initialize or Update Charts
                if (!sentimentChart && !deptChart) {
                    initCharts(data);
                } else {
                    // Update Sentiment Chart
                    sentimentChart.data.datasets[0].data = [
                        data.sentiments.Angry || 0,
                        data.sentiments.Frustrated || 0,
                        data.sentiments.Neutral || 0,
                        data.sentiments.Positive || 0
                    ];
                    sentimentChart.update();

                    // Update Dept Chart
                    deptChart.data.labels = Object.keys(data.departments);
                    deptChart.data.datasets[0].data = Object.values(data.departments);
                    deptChart.update();
                }
            })
            .catch(err => console.error("Error fetching analytics:", err));
    }

    // Initial Fetch
    fetchAnalytics();
    
    // Auto-refresh every 30 seconds
    setInterval(fetchAnalytics, 30000);
});
