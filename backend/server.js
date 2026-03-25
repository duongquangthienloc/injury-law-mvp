'use strict';

const express = require('express');
const bodyParser = require('body-parser');

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(bodyParser.json());
app.use(bodyParser.urlencoded({ extended: true }));

// API route for lead submission
app.post('/api/leads', (req, res) => {
    const lead = req.body;
    // Here you would typically save the lead to a database
    console.log('New lead submitted:', lead);
    res.status(201).json({ message: 'Lead submitted successfully!', lead });
});

app.listen(PORT, () => {
    console.log(`Server is running on port ${PORT}`);
});
