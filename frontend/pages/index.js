import React from 'react';

const IndexPage = () => {
  return (
    <div>
      <section className="hero">
        <h1>Welcome to the Injury Law MVP</h1>
        <p>We help you get the compensation you deserve.</p>
        <form>
          <label htmlFor="name">Name:</label>
          <input type="text" id="name" name="name" required />

          <label htmlFor="email">Email:</label>
          <input type="email" id="email" name="email" required />

          <button type="submit">Get Started</button>
        </form>
      </section>
    </div>
  );
};

export default IndexPage;