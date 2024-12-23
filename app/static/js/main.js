// Form submission handling
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('filterForm');
    const checkboxes = form.querySelectorAll('input[type="checkbox"]:not(.category-checkbox)');
    const selects = form.querySelectorAll('select');
    
    // Handle checkbox changes
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function() {
            form.submit();
        });
    });
    
    // Handle select changes
    selects.forEach(select => {
        select.addEventListener('change', function() {
            form.submit();
        });
    });
    
    // Handle search input
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                form.submit();
            }
        });
    }

    // Handle category multi-select
    const categoryCheckboxes = document.querySelectorAll('.category-checkbox');
    const categoryDropdownButton = document.getElementById('categoryDropdown');
    
    function updateCategoryButtonText() {
        const selectedCategories = Array.from(categoryCheckboxes)
            .filter(cb => cb.checked)
            .map(cb => cb.value);
        
        categoryDropdownButton.textContent = selectedCategories.length > 0
            ? selectedCategories.join(', ')
            : 'Categories';
    }

    categoryCheckboxes.forEach(checkbox => {
        checkbox.addEventListener('change', function(e) {
            e.stopPropagation(); // Prevent the dropdown from closing
            updateCategoryButtonText();
            form.submit();
        });
    });

    // Prevent dropdown from closing when clicking inside
    const categoryDropdown = document.querySelector('.dropdown-menu');
    if (categoryDropdown) {
        categoryDropdown.addEventListener('click', function(e) {
            e.stopPropagation();
        });
    }

    // Initialize category button text
    updateCategoryButtonText();
});

async function resetDatabase() {
    if (!confirm('Are you sure you want to reset the database? This action cannot be undone.')) {
        return;
    }
    
    try {
        const response = await fetch('/api/v1/admin/reset-database', {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error('Failed to reset database');
        }
        
        showToast('Database reset successfully', 'success');
        setTimeout(() => {
            window.location.reload();
        }, 1500);
    } catch (error) {
        console.error('Reset Error:', error);
        showToast(error.message || 'Error resetting database', 'error');
    }
}

async function fetchAllCases() {
    // Show progress UI
    const progressDiv = document.getElementById('taskProgress');
    const progressBar = document.getElementById('taskProgressBar');
    const taskStatus = document.getElementById('taskStatus');
    const processedCount = document.getElementById('processedCount');
    const totalCount = document.getElementById('totalCount');
    const timeRemaining = document.getElementById('timeRemaining');
    
    progressDiv.style.display = 'block';
    progressBar.style.width = '0%';
    progressBar.classList.add('progress-bar-animated');
    taskStatus.textContent = 'Starting...';
    
    try {
        // Start the fetch process
        const response = await fetch('/api/v1/admin/fetch-cases', {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error('Failed to start case fetching');
        }
        
        const data = await response.json();
        const taskId = data.task_id;
        
        // Create EventSource for SSE
        const eventSource = new EventSource(`/api/v1/task-status/${taskId}`);
        
        eventSource.onmessage = function(event) {
            const data = JSON.parse(event.data);
            
            // Update progress UI
            processedCount.textContent = data.processed_cases || 0;
            totalCount.textContent = data.total_cases || 'Unknown';
            
            const progress = data.progress_percentage || 0;
            progressBar.style.width = `${progress}%`;
            progressBar.setAttribute('aria-valuenow', progress);
            
            // Update status message
            taskStatus.textContent = data.message || data.status || 'Processing...';
            
            // Update time remaining
            if (data.estimated_time_remaining) {
                const minutes = Math.floor(data.estimated_time_remaining / 60);
                const seconds = data.estimated_time_remaining % 60;
                timeRemaining.textContent = `${minutes}m ${seconds}s`;
            }
            
            // Update stats
            updateStats({
                total_cases_checked: data.total_cases,
                medla_projects: data.medla_projects || 0
            });
            
            // Handle completion
            if (data.status === 'completed') {
                eventSource.close();
                progressBar.classList.remove('progress-bar-animated');
                progressBar.classList.add('bg-success');
                showToast('Successfully fetched all cases', 'success');
                setTimeout(() => {
                    window.location.reload();
                }, 1500);
            } else if (data.status === 'failed') {
                eventSource.close();
                progressBar.classList.remove('progress-bar-animated');
                progressBar.classList.add('bg-danger');
                showToast('Failed to fetch cases: ' + (data.error || 'Unknown error'), 'error');
            }
        };
        
        eventSource.onerror = function(error) {
            console.error('SSE Error:', error);
            eventSource.close();
            progressBar.classList.remove('progress-bar-animated');
            progressBar.classList.add('bg-danger');
            showToast('Error during case fetching', 'error');
        };
        
    } catch (error) {
        console.error('Fetch Error:', error);
        progressBar.classList.remove('progress-bar-animated');
        progressBar.classList.add('bg-danger');
        showToast(error.message || 'Error during case fetching', 'error');
    }
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

// Stats update functions
function updateStats(data) {
    function animateValue(element, value) {
        if (!element) return;
        
        // Add updating class for scale animation
        element.classList.add('updating');
        
        // Update the value
        element.textContent = value;
        
        // Remove the class after animation
        setTimeout(() => {
            element.classList.remove('updating');
        }, 200);
    }

    // Update total cases checked
    const totalCasesValue = document.querySelector('.stat-item:nth-child(1) .stat-value');
    if (totalCasesValue && data.total_cases_checked !== undefined) {
        animateValue(totalCasesValue, data.total_cases_checked.toLocaleString());
    }

    // Update Medla projects count and percentage
    const medlaProjectsValue = document.querySelector('.stat-item:nth-child(2) .stat-value');
    if (medlaProjectsValue && data.medla_projects !== undefined) {
        const percentage = data.total_cases_checked ? ((data.medla_projects / data.total_cases_checked) * 100).toFixed(1) : 0;
        animateValue(medlaProjectsValue, `${data.medla_projects.toLocaleString()} (${percentage}%)`);
    }

    // Update last update time
    const lastUpdateValue = document.querySelector('.stat-item:nth-child(3) .stat-value');
    if (lastUpdateValue) {
        const now = new Date();
        const timeStr = now.toLocaleTimeString(undefined, {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
        const dateStr = now.toLocaleDateString(undefined, {
            month: 'short',
            day: 'numeric'
        });
        animateValue(lastUpdateValue, `${timeStr}, ${dateStr}`);
    }
}

// ... rest of existing code ... 