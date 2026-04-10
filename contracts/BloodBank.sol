// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract BloodBank {
    struct Donation {
        address donorAddress;
        string bloodType;
        uint256 quantity;
        uint256 timestamp;
    }

    struct Request {
        uint256 hospitalId;
        string bloodType;
        uint256 quantity;
        string urgency;
        string status; // Pending, Approved, Fulfilled, Rejected
        uint256 timestamp;
    }

    Donation[] public donations;
    Request[] public requests;

    // Mapping to track total available blood (simple inventory on-chain)
    mapping(string => uint256) public inventory;

    event DonationRecorded(uint256 indexed donationId, address donor, string bloodType, uint256 quantity);
    event RequestCreated(uint256 indexed requestId, uint256 hospitalId, string bloodType, uint256 quantity);
    event RequestFulfilled(uint256 indexed requestId, uint256 hospitalId, string bloodType);

    function recordDonation(address _donorAddress, string memory _bloodType, uint256 _quantity) public {
        require(_quantity > 0, "Quantity must be > 0");
        donations.push(Donation(_donorAddress, _bloodType, _quantity, block.timestamp));
        inventory[_bloodType] += _quantity;
        emit DonationRecorded(donations.length - 1, _donorAddress, _bloodType, _quantity);
    }

    function createRequest(uint256 _hospitalId, string memory _bloodType, uint256 _quantity, string memory _urgency) public {
        require(_quantity > 0, "Quantity must be > 0");
        requests.push(Request(_hospitalId, _bloodType, _quantity, _urgency, "Pending", block.timestamp));
        emit RequestCreated(requests.length - 1, _hospitalId, _bloodType, _quantity);
    }

    function fulfillRequest(uint256 _requestId) public {
        require(_requestId < requests.length, "Invalid request ID");
        Request storage req = requests[_requestId];
        require(keccak256(bytes(req.status)) == keccak256(bytes("Pending")), "Request not pending");
        require(inventory[req.bloodType] >= req.quantity, "Insufficient inventory");

        inventory[req.bloodType] -= req.quantity;
        req.status = "Fulfilled";
        emit RequestFulfilled(_requestId, req.hospitalId, req.bloodType);
    }

    function getInventory(string memory _bloodType) public view returns (uint256) {
        return inventory[_bloodType];
    }

    function getRequestCount() public view returns (uint256) {
        return requests.length;
    }

    function getDonationCount() public view returns (uint256) {
        return donations.length;
    }
}