import QtQuick
import qs
import qs.components
import qs.services

// Bar > Widgets: the settings of single bar widgets: the clock, its calendar popup and the music widget. Keys mirror
// settings.py (clock.*, calendar.*, media.*); the widgets read them live (docs/modules/calendar.md, media.md). The privacy
// indicator's switches are on Privacy and wellbeing, next to what is in use right now. Until 2026-10-28 the clock and
// calendar were a Date and time page (with the calendar also on the Bar page) and the music width was on the Sound page.
SettingsPage {
    note: "The time zone is set by the system: timedatectl set-timezone."

    SettingsSection {
        title: "Clock"
        SettingToggle { label: "24-hour clock"; hint: "Off: 12-hour, without AM or PM"; key: "clock.hour24" }
        SettingToggle { label: "Show the date"; hint: "The weekday, day and month before the time"; key: "clock.date" }
        SettingToggle { label: "Full date on hover"; hint: "Resting the pointer on the clock shows a small card with the full date"; key: "clock.hoverDate" }
        SettingToggle { label: "Show seconds"; hint: "The clock then redraws every second instead of every minute, which costs a little battery"; key: "clock.seconds" }
    }

    SettingsSection {
        title: "Calendar"
        description: "Click the clock to open it."
        SettingChoice {
            label: "Week starts on"; key: "calendar.weekStart"
            model: [{ value: "mon", label: "Monday" }, { value: "sun", label: "Sunday" }, { value: "sat", label: "Saturday" }]
        }
        SettingToggle { label: "Week numbers"; key: "calendar.weekNumbers" }
        SettingToggle { label: "Moon phase"; hint: "Shown with the selected day"; key: "calendar.moon" }
    }

    SettingsSection {
        title: "Music"
        SettingSlider { label: "Longest width"; hint: "The title is cut to fit, and to make room for the buttons while the pointer is on it"; key: "media.maxWidth"; from: 120; to: 400; step: 10; suffix: " px" }
    }
}
