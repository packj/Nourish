// Nourish - Calendar UI Controller

document.addEventListener('DOMContentLoaded', () => {
    const slug = window.SET_SLUG;
    if (!slug) return;

    let currentYear = window.INITIAL_YEAR || new Date().getFullYear();
    let currentMonth = window.INITIAL_MONTH || (new Date().getMonth() + 1);

    const monthTitle = document.getElementById('calendar-month-title');
    const calendarGrid = document.getElementById('calendar-grid');
    const upcomingList = document.getElementById('upcoming-open-list');
    const prevBtn = document.getElementById('prev-month-btn');
    const nextBtn = document.getElementById('next-month-btn');
    const todayBtn = document.getElementById('view-today-btn');

    // Modal elements
    const modal = document.getElementById('booking-modal');
    const modalDateDisplay = document.getElementById('modal-date-display');
    const formMealDate = document.getElementById('form-meal-date');
    const closeModalBtn = document.getElementById('close-modal-btn');
    const cancelModalBtn = document.getElementById('cancel-modal-btn');
    const hostNameInput = document.getElementById('form-host-name');

    async function loadCalendar(year, month) {
        calendarGrid.innerHTML = '<div class="loading-spinner py-4 text-center">Loading calendar...</div>';
        try {
            const resp = await fetch(`/api/calendar/${slug}?year=${year}&month=${month}`);
            if (!resp.ok) throw new Error('Failed to load calendar');
            const data = await resp.json();
            renderCalendar(data);
        } catch (err) {
            console.error(err);
            calendarGrid.innerHTML = '<div class="alert alert-error">Unable to load calendar data.</div>';
        }
    }

    function renderCalendar(data) {
        monthTitle.textContent = `${data.month_name} ${data.year}`;
        currentYear = data.year;
        currentMonth = data.month;

        calendarGrid.innerHTML = '';
        upcomingList.innerHTML = '';

        const days = data.days;
        if (!days || days.length === 0) return;

        // Determine day of week for 1st day of month (0 = Sunday, 6 = Saturday)
        const firstDate = new Date(data.year, data.month - 1, 1);
        const startDayIndex = firstDate.getDay();

        // Add blank cells for padding before the 1st
        for (let i = 0; i < startDayIndex; i++) {
            const emptyCell = document.createElement('div');
            emptyCell.className = 'calendar-cell is-empty';
            calendarGrid.appendChild(emptyCell);
        }

        let openSlotsCount = 0;

        days.forEach(day => {
            const cell = document.createElement('div');
            cell.className = `calendar-cell status-${day.status}`;
            if (day.is_today) cell.classList.add('is-today');
            if (day.is_past) cell.classList.add('is-past');

            // Cell Header
            const cellHeader = document.createElement('div');
            cellHeader.className = 'cell-header';

            const dayNum = document.createElement('span');
            dayNum.className = 'day-number';
            dayNum.textContent = day.day;
            cellHeader.appendChild(dayNum);

            // Status Badge
            const badge = document.createElement('span');
            badge.className = `cell-badge badge-${day.status}-slot`;
            
            if (day.status === 'open') {
                badge.textContent = 'Open';
                // Click to book
                cell.addEventListener('click', () => openBookingModal(day.date, day.day_name, data.month_name, day.day));
                
                // Add to mobile upcoming list if current or future
                if (!day.is_past && openSlotsCount < 10) {
                    addOpenSlotToList(day, data.month_name);
                    openSlotsCount++;
                }
            } else if (day.status === 'booked') {
                badge.textContent = 'Booked';
            } else if (day.status === 'blocked') {
                badge.textContent = 'Blocked';
                badge.title = day.blocked_reason || 'Unavailable';
            } else if (day.status === 'past') {
                badge.textContent = 'Past';
            }
            cellHeader.appendChild(badge);
            cell.appendChild(cellHeader);

            // Cell Content (Host name if booked, reason if blocked)
            const cellContent = document.createElement('div');
            cellContent.className = 'cell-content';
            if (day.status === 'booked' && day.booking) {
                cellContent.innerHTML = `<span class="host-name-tag">🍽️ ${escapeHtml(day.booking.host_name)}</span>`;
            } else if (day.status === 'blocked' && day.blocked_reason) {
                cellContent.innerHTML = `<span class="text-muted text-xs">${escapeHtml(day.blocked_reason)}</span>`;
            }
            cell.appendChild(cellContent);

            calendarGrid.appendChild(cell);
        });

        if (openSlotsCount === 0) {
            upcomingList.innerHTML = '<p class="text-muted text-sm">No open dinner slots in this month.</p>';
        }
    }

    function addOpenSlotToList(day, monthName) {
        const slotCard = document.createElement('div');
        slotCard.className = 'open-slot-card';
        slotCard.innerHTML = `
            <div>
                <div class="slot-date-text">${monthName} ${day.day}</div>
                <div class="slot-day-name">${day.day_name}</div>
            </div>
            <span class="btn btn-sm btn-primary">Sign Up &rarr;</span>
        `;
        slotCard.addEventListener('click', () => {
            openBookingModal(day.date, day.day_name, monthName, day.day);
        });
        upcomingList.appendChild(slotCard);
    }

    function openBookingModal(dateStr, dayName, monthName, dayNum) {
        formMealDate.value = dateStr;
        modalDateDisplay.textContent = `${dayName}, ${monthName} ${dayNum}`;
        modal.classList.remove('hidden');
        if (hostNameInput) {
            setTimeout(() => hostNameInput.focus(), 100);
        }
    }

    function closeModal() {
        modal.classList.add('hidden');
    }

    // Modal close listeners
    if (closeModalBtn) closeModalBtn.addEventListener('click', closeModal);
    if (cancelModalBtn) cancelModalBtn.addEventListener('click', closeModal);
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeModal();
        });
    }

    // Month Navigation Listeners
    if (prevBtn) {
        prevBtn.addEventListener('click', () => {
            if (currentMonth === 1) {
                currentYear--;
                currentMonth = 12;
            } else {
                currentMonth--;
            }
            loadCalendar(currentYear, currentMonth);
        });
    }

    if (nextBtn) {
        nextBtn.addEventListener('click', () => {
            if (currentMonth === 12) {
                currentYear++;
                currentMonth = 1;
            } else {
                currentMonth++;
            }
            loadCalendar(currentYear, currentMonth);
        });
    }

    if (todayBtn) {
        todayBtn.addEventListener('click', () => {
            const now = new Date();
            loadCalendar(now.getFullYear(), now.getMonth() + 1);
        });
    }

    // Escape HTML helper
    function escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Initial load
    loadCalendar(currentYear, currentMonth);
});
