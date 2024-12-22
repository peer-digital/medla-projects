async function resetDatabase() {
    if (!confirm('Are you sure you want to reset the database? This action cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch('/api/v1/admin/reset-database', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('Database reset started', 'info');
            startPolling(data.task_id, 'Resetting database...');
        } else {
            showToast(data.detail || 'Failed to reset database', 'error');
        }
    } catch (error) {
        showToast('Error resetting database', 'error');
    }
}

async function fetchAllCases() {
    try {
        const response = await fetch('/api/v1/admin/fetch-all-cases', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('Started fetching all cases', 'info');
            startPolling(data.task_id, 'Fetching cases...');
        } else {
            showToast(data.detail || 'Failed to start fetch', 'error');
        }
    } catch (error) {
        showToast('Error starting fetch', 'error');
    }
}

async function fetchBookmarkedDetails() {
    try {
        const response = await fetch('/api/v1/admin/fetch-bookmarked-details', {
            method: 'POST'
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('Started fetching bookmarked details', 'info');
            startPolling(data.task_id, 'Fetching details...');
        } else {
            showToast(data.detail || 'Failed to start fetch', 'error');
        }
    } catch (error) {
        showToast('Error starting fetch', 'error');
    }
}

async function startPolling(taskId, initialMessage) {
    // Store task info in localStorage
    localStorage.setItem('activeTaskId', taskId);
    localStorage.setItem('taskMessage', initialMessage);
    
    let isRunning = true;
    let lastProcessed = 0;
    let statusInterval, tableInterval;  // Declare intervals at function scope
    
    // Show progress UI
    const progressDiv = document.getElementById('taskProgress');
    const progressBar = document.getElementById('taskProgressBar');
    const taskTitle = document.getElementById('taskTitle');
    const taskStatus = document.getElementById('taskStatus');
    const processedCount = document.getElementById('processedCount');
    const totalCount = document.getElementById('totalCount');
    const timeRemaining = document.getElementById('timeRemaining');
    const taskErrors = document.getElementById('taskErrors');
    const tableContainer = document.querySelector('.table-responsive');
    const noResults = document.getElementById('noResults');
    
    // Function to clean up intervals and storage
    function cleanup() {
        if (statusInterval) clearInterval(statusInterval);
        if (tableInterval) clearInterval(tableInterval);
        localStorage.removeItem('activeTaskId');
        localStorage.removeItem('taskMessage');
    }
    
    progressDiv.style.display = 'block';
    taskErrors.style.display = 'none';
    taskErrors.querySelector('ul').innerHTML = '';
    taskTitle.textContent = initialMessage;
    
    // Initialize progress bar
    progressBar.classList.add('progress-bar-animated');
    progressBar.classList.remove('bg-success', 'bg-danger');
    progressBar.style.width = '0%';
    progressBar.setAttribute('aria-valuenow', 0);

    // Function to refresh the table with latest data
    async function refreshTable() {
        try {
            const response = await fetch(window.location.href);
            const text = await response.text();
            const parser = new DOMParser();
            const doc = parser.parseFromString(text, 'text/html');
            
            // Update table body
            const newTableBody = doc.querySelector('#casesTable tbody');
            const currentTableBody = document.querySelector('#casesTable tbody');
            if (newTableBody && currentTableBody) {
                currentTableBody.innerHTML = newTableBody.innerHTML;
            }
            
            // Update case count
            const newCaseCount = doc.querySelector('#caseCount');
            const currentCaseCount = document.getElementById('caseCount');
            if (newCaseCount && currentCaseCount) {
                currentCaseCount.textContent = newCaseCount.textContent;
            }
            
            // Show/hide table and no results message
            const hasResults = newTableBody && newTableBody.children.length > 0;
            if (hasResults) {
                tableContainer.style.display = 'block';
                noResults.style.display = 'none';
            } else {
                tableContainer.style.display = 'none';
                noResults.style.display = 'block';
            }
        } catch (error) {
            console.error('Error refreshing table:', error);
        }
    }

    // Function to check task status
    async function checkTaskStatus() {
        try {
            const response = await fetch(`/api/v1/task-status/${taskId}`);
            if (!response.ok) {
                throw new Error('Failed to fetch task status');
            }
            
            const data = await response.json();
            
            // Update progress UI
            if (data.progress_percentage !== undefined) {
                progressBar.style.width = `${data.progress_percentage}%`;
                progressBar.setAttribute('aria-valuenow', data.progress_percentage);
            }
            
            if (data.total_cases !== undefined) {
                totalCount.textContent = data.total_cases;
            }
            
            if (data.processed_cases !== undefined) {
                processedCount.textContent = data.processed_cases;
                
                // Trigger table refresh if we have new cases
                if (data.processed_cases > lastProcessed) {
                    await refreshTable();
                    lastProcessed = data.processed_cases;
                }
            }
            
            // Update task status
            if (data.status) {
                taskStatus.textContent = data.status;
            }
            
            // Show any errors
            if (data.errors && data.errors.length > 0) {
                taskErrors.style.display = 'block';
                const errorList = taskErrors.querySelector('ul');
                errorList.innerHTML = ''; // Clear existing errors
                data.errors.forEach(error => {
                    const li = document.createElement('li');
                    li.textContent = error;
                    li.className = 'text-danger';
                    errorList.appendChild(li);
                });
            }
            
            // Handle completion states
            if (data.status === 'completed') {
                isRunning = false;
                cleanup();
                showToast('Task completed successfully', 'success');
                progressBar.classList.remove('progress-bar-animated');
                progressBar.classList.add('bg-success');
                
                // Final refresh and cleanup
                await refreshTable();
                setTimeout(() => {
                    progressDiv.style.display = 'none';
                }, 1500);
                return true;
            } else if (data.status === 'failed') {
                isRunning = false;
                cleanup();
                showToast(data.error || 'Task failed', 'error');
                progressBar.classList.remove('progress-bar-animated');
                progressBar.classList.add('bg-danger');
                setTimeout(() => {
                    progressDiv.style.display = 'none';
                }, 1500);
                return true;
            }
            
            return false;
        } catch (error) {
            console.error('Error checking task status:', error);
            showToast('Error checking task status', 'error');
            isRunning = false;
            cleanup();
            progressBar.classList.remove('progress-bar-animated');
            progressBar.classList.add('bg-danger');
            setTimeout(() => {
                progressDiv.style.display = 'none';
            }, 1500);
            return true;
        }
    }

    // Start polling loops
    statusInterval = setInterval(async () => {
        if (!isRunning) {
            cleanup();
            return;
        }
        const isDone = await checkTaskStatus();
        if (isDone) {
            cleanup();
        }
    }, 1000);

    tableInterval = setInterval(async () => {
        if (!isRunning) {
            cleanup();
            return;
        }
        await refreshTable();
    }, 2000);

    // Initial checks
    await checkTaskStatus();
    await refreshTable();
}

// Helper function to show toast notifications
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    
    document.body.appendChild(toast);
    
    // Trigger reflow
    toast.offsetHeight;
    
    // Add show class
    toast.classList.add('show');
    
    // Remove after 3 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// Add initialization code at the bottom of the file
document.addEventListener('DOMContentLoaded', async () => {
    // Check for active task
    const activeTaskId = localStorage.getItem('activeTaskId');
    const taskMessage = localStorage.getItem('taskMessage');
    
    if (activeTaskId) {
        try {
            // Check if task is still running
            const response = await fetch(`/api/v1/task-status/${activeTaskId}`);
            const data = await response.json();
            
            if (data.status && !['completed', 'failed'].includes(data.status)) {
                // Task is still running, restart polling
                startPolling(activeTaskId, taskMessage || 'Processing...');
            } else {
                // Task is done, clean up
                localStorage.removeItem('activeTaskId');
                localStorage.removeItem('taskMessage');
            }
        } catch (error) {
            console.error('Error checking task status:', error);
            localStorage.removeItem('activeTaskId');
            localStorage.removeItem('taskMessage');
        }
    }
}); 