/**
 * Simple Resize Handler - Clean Implementation
 * Replaces the complex resize logic with a straightforward approach
 */

function initializeFlexboxResize() {
    const sidebar = document.querySelector('.sidebar');
    const chat = document.querySelector('.chat-container');
    const tasks = document.querySelector('.tasks-container');
    const bottomRow = document.querySelector('.ide-bottom-row');
    
    const sidebarHandle = document.getElementById('resizeSidebar');
    const chatHandle = document.getElementById('resizeChat');
    const terminalHandle = document.getElementById('resizeTerminal');
    const tasksHandle = document.getElementById('resizeTasks');
    
    console.log('Initializing flexbox resize...');
    
    if (!sidebar || !chat || !tasks || !bottomRow) {
        console.error('Layout elements not found');
        return;
    }
    
    if (!sidebarHandle || !chatHandle || !terminalHandle || !tasksHandle) {
        console.error('Resize handles not found');
        return;
    }
    
    let isResizing = false;
    let currentHandle = null;
    let startPos = 0;
    
    // Reset layout function
    function resetLayout() {
        sidebar.style.width = '300px';
        chat.style.width = '300px';
        tasks.style.width = '300px';
        bottomRow.style.height = '200px';
        
        // Reset handle positions
        sidebarHandle.style.left = '296px';
        chatHandle.style.right = '296px';
        terminalHandle.style.bottom = '196px';
        tasksHandle.style.left = '296px';
        
        console.log('Flexbox layout reset to defaults');
    }
    
    // Make reset globally accessible
    window.resetLayout = resetLayout;
    
    // Sidebar resize
    sidebarHandle.addEventListener('mousedown', (e) => {
        isResizing = true;
        currentHandle = 'sidebar';
        startPos = e.clientX;
        document.body.style.cursor = 'col-resize';
        e.preventDefault();
    });
    
    // Chat resize
    chatHandle.addEventListener('mousedown', (e) => {
        isResizing = true;
        currentHandle = 'chat';
        startPos = e.clientX;
        document.body.style.cursor = 'col-resize';
        e.preventDefault();
    });
    
    // Terminal resize
    terminalHandle.addEventListener('mousedown', (e) => {
        isResizing = true;
        currentHandle = 'terminal';
        startPos = e.clientY;
        document.body.style.cursor = 'row-resize';
        e.preventDefault();
    });
    
    // Tasks resize
    tasksHandle.addEventListener('mousedown', (e) => {
        isResizing = true;
        currentHandle = 'tasks';
        startPos = e.clientX;
        document.body.style.cursor = 'col-resize';
        e.preventDefault();
    });
    
    // Mouse move
    document.addEventListener('mousemove', (e) => {
        if (!isResizing) return;
        
        if (currentHandle === 'sidebar') {
            const delta = e.clientX - startPos;
            const newWidth = Math.max(200, Math.min(600, 300 + delta));
            sidebar.style.width = newWidth + 'px';
            sidebarHandle.style.left = (newWidth - 4) + 'px';
            tasksHandle.style.left = (newWidth - 4) + 'px';
        } else if (currentHandle === 'chat') {
            const delta = startPos - e.clientX;
            const newWidth = Math.max(200, Math.min(600, 300 + delta));
            chat.style.width = newWidth + 'px';
            chatHandle.style.right = (newWidth - 4) + 'px';
        } else if (currentHandle === 'terminal') {
            const delta = startPos - e.clientY;
            const newHeight = Math.max(100, Math.min(400, 200 + delta));
            bottomRow.style.height = newHeight + 'px';
            terminalHandle.style.bottom = (newHeight - 4) + 'px';
        } else if (currentHandle === 'tasks') {
            const delta = e.clientX - startPos;
            const newWidth = Math.max(200, Math.min(400, 300 + delta));
            tasks.style.width = newWidth + 'px';
        }
        
        // Trigger Monaco resize
        if (window.ide && window.ide.editor) {
            setTimeout(() => window.ide.editor.layout(), 10);
        }
    });
    
    // Mouse up
    document.addEventListener('mouseup', () => {
        if (!isResizing) return;
        
        isResizing = false;
        currentHandle = null;
        document.body.style.cursor = '';
    });
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Reset layout first
    const sidebar = document.querySelector('.sidebar');
    const chat = document.querySelector('.chat-container');
    const tasks = document.querySelector('.tasks-container');
    const bottomRow = document.querySelector('.ide-bottom-row');
    
    if (sidebar && chat && tasks && bottomRow) {
        sidebar.style.width = '300px';
        chat.style.width = '300px';
        tasks.style.width = '300px';
        bottomRow.style.height = '200px';
        console.log('Initial flexbox layout set');
    }
    
    // Initialize resize after a short delay
    setTimeout(initializeFlexboxResize, 100);
});