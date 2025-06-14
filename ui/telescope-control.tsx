"use client"

import { useEffect } from "react"
import { NotificationPanels } from "./notification-panels"
import { LocationManagement } from "./location-management"
import { TelescopeProvider } from "./context/TelescopeContext"
import { Header } from "./components/telescope/Header"
import { StatusAlerts } from "./components/telescope/StatusAlerts"
import { CameraView } from "./components/telescope/CameraView"
import { ControlPanel } from "./components/telescope/ControlPanel"
import { PlanningPanel } from "./components/telescope/modals/PlanningPanel"
import { NotificationSettings as NotificationSettingsModal } from "./components/telescope/modals/NotificationSettings"
import { NotificationHistory as NotificationHistoryModal } from "./components/telescope/modals/NotificationHistory"
import { KeyboardHelp as KeyboardHelpModal } from "./components/telescope/modals/KeyboardHelp"
import { DataPersistenceManager } from "./components/telescope/DataPersistenceManager"
import { useTelescopeContext } from "./context/TelescopeContext"
import { PictureInPictureOverlay } from "./components/telescope/PictureInPictureOverlay"
import { PipOverlayControls } from "./components/telescope/PipOverlayControls"
import { DataManagementSettings } from "./components/telescope/modals/DataManagementSettings"
import { EquipmentManager } from "./components/telescope/modals/EquipmentManager"

function TelescopeControlContent() {
  const {
    showPlanningPanel,
    showNotificationSettings,
    showNotificationHistory,
    showKeyboardHelp,
    showLocationManager,
    isControlsCollapsed,
    handleKeyDown,
    showDataManagementSettings,
    showEquipmentManager,
  } = useTelescopeContext()

  // Set up keyboard event listeners
  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown)
    return () => {
      window.removeEventListener("keydown", handleKeyDown)
    }
  }, [handleKeyDown])

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      <div className="max-w-7xl mx-auto">
        <Header />
        <StatusAlerts />

        <div className={`grid gap-6 ${isControlsCollapsed ? "grid-cols-1" : "lg:grid-cols-4"}`}>
          <div className={`${isControlsCollapsed ? "col-span-1" : "lg:col-span-3"}`}>
            <CameraView />
          </div>
          {!isControlsCollapsed && (
            <div className="lg:col-span-1">
              <ControlPanel />
            </div>
          )}
        </div>

        {/* Modals */}
        {showPlanningPanel && <PlanningPanel />}
        {showNotificationSettings && <NotificationSettingsModal />}
        {showNotificationHistory && <NotificationHistoryModal />}
        {showKeyboardHelp && <KeyboardHelpModal />}
        {showLocationManager && <LocationManagement onClose={() => {}} />}
        {showDataManagementSettings && <DataManagementSettings />}
        {showEquipmentManager && <EquipmentManager />}

        {/* Picture-in-Picture Overlay */}
        <PictureInPictureOverlay />

        {/* PiP Overlay Controls - Now inside TelescopeProvider */}
        <PipOverlayControls />

        <DataPersistenceManager />
      </div>
    </div>
  )
}

export default function TelescopeControl() {
  return (
    <TelescopeProvider>
      <TelescopeControlContent />
      <NotificationPanels notifications={[]} onDismiss={() => {}} onMarkAsRead={() => {}} />
    </TelescopeProvider>
  )
}
