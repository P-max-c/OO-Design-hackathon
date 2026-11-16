"""
Parking Management System - Python implementation of the UML class diagram.

Relationships implemented:
  Driver  --makes-->    Booking
  Vehicle --usedFor-->  Booking
  ParkingLot --contains--> ParkingFloor --contains--> ParkingSlot
  Booking --paidBy-->   Payment
  ParkingSystem --coordinates--> ParkingManager --uses--> ParkingAvailabilityMonitor

Design patterns visible in the diagram:
  - Singleton: ParkingSystem (getInstance)
  - Observer:  ParkingAvailabilityMonitor (notifyObservers)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional


# --------------------------------------------------------------------------
# Enums (types used by attributes in the diagram)
# --------------------------------------------------------------------------
class SlotStatus(Enum):
    AVAILABLE = "AVAILABLE"
    OCCUPIED = "OCCUPIED"
    MAINTENANCE = "MAINTENANCE"


class BookingStatus(Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class PaymentStatus(Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


# --------------------------------------------------------------------------
# Parking structure: ParkingLot -> ParkingFloor -> ParkingSlot
# --------------------------------------------------------------------------
class ParkingSlot:
    def __init__(self, slot_id: str, slot_type: str):
        self.slot_id = slot_id
        self.slot_type = slot_type            # e.g. "CAR", "BIKE"
        self.status = SlotStatus.AVAILABLE

    def mark_occupied(self) -> None:
        self.status = SlotStatus.OCCUPIED

    def mark_available(self) -> None:
        self.status = SlotStatus.AVAILABLE

    def __repr__(self) -> str:
        return f"ParkingSlot({self.slot_id}, {self.slot_type}, {self.status.name})"


class ParkingFloor:
    def __init__(self, floor_no: int):
        self.floor_no = floor_no
        self._slots: List[ParkingSlot] = []   # +contains

    def add_slot(self, slot: ParkingSlot) -> None:
        self._slots.append(slot)

    def get_slots(self) -> List[ParkingSlot]:
        return list(self._slots)


class ParkingLot:
    def __init__(self, lot_id: str, name: str, address: str):
        self.lot_id = lot_id
        self.name = name
        self.address = address
        self._floors: List[ParkingFloor] = []  # +contains

    def add_floor(self, floor: ParkingFloor) -> None:
        self._floors.append(floor)

    def get_floors(self) -> List[ParkingFloor]:
        return list(self._floors)

    def get_available_slots(self, slot_type: Optional[str] = None) -> List[ParkingSlot]:
        return [
            slot
            for floor in self._floors
            for slot in floor.get_slots()
            if slot.status == SlotStatus.AVAILABLE
            and (slot_type is None or slot.slot_type == slot_type)
        ]


# --------------------------------------------------------------------------
# Vehicle, Payment, Booking
# --------------------------------------------------------------------------
class Vehicle:
    def __init__(self, vehicle_no: str, vehicle_type: str):
        self.vehicle_no = vehicle_no
        self.vehicle_type = vehicle_type

    def get_vehicle_details(self) -> str:
        return f"{self.vehicle_type} [{self.vehicle_no}]"


class Payment:
    def __init__(self, payment_id: str, amount: float):
        self.payment_id = payment_id
        self.amount = amount
        self.status = PaymentStatus.PENDING

    def process_payment(self) -> bool:
        # Placeholder for a real payment gateway call.
        if self.amount <= 0:
            self.status = PaymentStatus.FAILED
            return False
        self.status = PaymentStatus.SUCCESS
        return True

    def refund(self) -> bool:
        if self.status != PaymentStatus.SUCCESS:
            return False
        self.status = PaymentStatus.REFUNDED
        return True


class Booking:
    def __init__(
        self,
        booking_id: str,
        driver: "Driver",          # +makes
        vehicle: Vehicle,          # +usedFor
        slot: ParkingSlot,
        start_time: datetime,
        end_time: datetime,
        payment: Payment,          # +paidBy
    ):
        self.booking_id = booking_id
        self.driver = driver
        self.vehicle = vehicle
        self.slot = slot
        self.start_time = start_time
        self.end_time = end_time
        self.payment = payment
        self.status = BookingStatus.PENDING

    def confirm(self) -> bool:
        if self.status != BookingStatus.PENDING:
            return False
        if not self.payment.process_payment():
            return False
        self.slot.mark_occupied()
        self.status = BookingStatus.CONFIRMED
        return True

    def cancel(self) -> bool:
        if self.status == BookingStatus.CANCELLED:
            return False
        if self.status == BookingStatus.CONFIRMED:
            self.payment.refund()
        self.slot.mark_available()
        self.status = BookingStatus.CANCELLED
        return True


# --------------------------------------------------------------------------
# Observer: ParkingAvailabilityMonitor
# --------------------------------------------------------------------------
class ParkingAvailabilityMonitor:
    """Subject in the Observer pattern. Observers need an `update(lot_name, count)` method."""

    def __init__(self):
        self._observers: list = []

    def register_observer(self, observer) -> None:
        if observer not in self._observers:
            self._observers.append(observer)

    def remove_observer(self, observer) -> None:
        if observer in self._observers:
            self._observers.remove(observer)

    def notify_observers(self, lot: Optional[ParkingLot] = None) -> None:
        if lot is None:
            return
        count = len(lot.get_available_slots())
        for observer in self._observers:
            observer.update(lot.name, count)


# --------------------------------------------------------------------------
# ParkingManager and ParkingSystem (Singleton)
# --------------------------------------------------------------------------
class ParkingManager:
    def __init__(self, monitor: ParkingAvailabilityMonitor):
        self.monitor = monitor                # +uses

    def allocate_slot(self, lot: ParkingLot, slot_type: str) -> Optional[ParkingSlot]:
        available = lot.get_available_slots(slot_type)
        if not available:
            return None
        slot = available[0]
        slot.mark_occupied()                  # reserve it immediately
        self.monitor.notify_observers(lot)
        return slot


class ParkingSystem:
    _instance: Optional["ParkingSystem"] = None   # - instance: ParkingSystem

    def __init__(self):
        if ParkingSystem._instance is not None:
            raise RuntimeError("Use ParkingSystem.get_instance()")
        self.monitor = ParkingAvailabilityMonitor()
        self.manager = ParkingManager(self.monitor)   # +coordinates
        self.bookings: List[Booking] = []

    @classmethod
    def get_instance(cls) -> "ParkingSystem":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def create_booking(
        self,
        driver: "Driver",
        vehicle: Vehicle,
        lot: ParkingLot,
        start_time: datetime,
        end_time: datetime,
        rate_per_hour: float = 20.0,
    ) -> Optional[Booking]:
        slot = self.manager.allocate_slot(lot, vehicle.vehicle_type)
        if slot is None:
            return None

        hours = max((end_time - start_time).total_seconds() / 3600, 1)
        payment = Payment(_new_id("PAY"), round(hours * rate_per_hour, 2))
        booking = Booking(_new_id("BKG"), driver, vehicle, slot, start_time, end_time, payment)

        if not booking.confirm():
            slot.mark_available()
            self.monitor.notify_observers(lot)
            return None

        self.bookings.append(booking)
        return booking


# --------------------------------------------------------------------------
# Actors: Driver and Admin
# --------------------------------------------------------------------------
class Driver:
    def __init__(self, driver_id: str, name: str, phone: str):
        self.driver_id = driver_id
        self.name = name
        self.phone = phone

    def search_parking(self, lots: List[ParkingLot], slot_type: Optional[str] = None) -> dict:
        """Return {lot name: number of available slots}."""
        return {lot.name: len(lot.get_available_slots(slot_type)) for lot in lots}

    def book_slot(
        self,
        vehicle: Vehicle,
        lot: ParkingLot,
        start_time: datetime,
        end_time: datetime,
    ) -> Optional[Booking]:
        return ParkingSystem.get_instance().create_booking(
            self, vehicle, lot, start_time, end_time
        )

    # Observer callback
    def update(self, lot_name: str, available: int) -> None:
        print(f"[Notification to {self.name}] {lot_name}: {available} slot(s) available")


class Admin:
    def __init__(self, admin_id: str, name: str):
        self.admin_id = admin_id
        self.name = name

    def add_parking_floor(self, lot: ParkingLot, floor: ParkingFloor) -> None:
        lot.add_floor(floor)

    def update_slot_status(self, slot: ParkingSlot, status: SlotStatus) -> None:
        slot.status = status


# --------------------------------------------------------------------------
# Demo
# --------------------------------------------------------------------------
if __name__ == "__main__":
    # Admin builds the lot
    admin = Admin("A1", "Ravi")
    lot = ParkingLot("L1", "City Mall Parking", "MG Road, Bengaluru")

    for floor_no in (1, 2):
        floor = ParkingFloor(floor_no)
        for i in range(1, 3):
            floor.add_slot(ParkingSlot(f"F{floor_no}-CAR-{i}", "CAR"))
        floor.add_slot(ParkingSlot(f"F{floor_no}-BIKE-1", "BIKE"))
        admin.add_parking_floor(lot, floor)

    # Driver registers for availability notifications
    driver = Driver("D1", "Puneet", "9999999999")
    system = ParkingSystem.get_instance()
    system.monitor.register_observer(driver)

    # Search and book
    print("Search:", driver.search_parking([lot], "CAR"))
    car = Vehicle("KA01AB1234", "CAR")
    start = datetime.now()
    booking = driver.book_slot(car, lot, start, start + timedelta(hours=3))

    if booking:
        print(f"Booked {booking.slot.slot_id} | status={booking.status.name} "
              f"| amount={booking.payment.amount} | payment={booking.payment.status.name}")

    # Cancel -> refund
    if booking:
        booking.cancel()
        print(f"After cancel: booking={booking.status.name}, "
              f"payment={booking.payment.status.name}, slot={booking.slot.status.name}")

    # Admin marks a slot for maintenance
    admin.update_slot_status(lot.get_floors()[0].get_slots()[0], SlotStatus.MAINTENANCE)
    print("Search after maintenance:", driver.search_parking([lot], "CAR"))

    # Singleton check
    print("Singleton works:", ParkingSystem.get_instance() is system)
