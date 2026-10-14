'use client';

import React, { useState } from 'react';
import { Mail, MapPin, Phone, Send, CheckCircle2 } from 'lucide-react';
import { motion } from 'motion/react';

export default function ContactPage() {
  const [isSubmitted, setIsSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setTimeout(() => setIsSubmitted(true), 1000);
  };

  return (
    <div className="flex-1 bg-slate-50 dark:bg-slate-950 py-16 px-4 sm:px-6 lg:px-8 overflow-hidden relative">
      <div className="absolute top-0 right-0 w-full h-full overflow-hidden pointer-events-none z-0">
        <div className="absolute top-[-10%] right-[-5%] w-[40%] h-[50%] rounded-full bg-indigo-100 dark:bg-indigo-900/40 blur-[100px] opacity-60" />
        <div className="absolute bottom-[-10%] left-[-5%] w-[40%] h-[50%] rounded-full bg-blue-100 dark:bg-blue-900/40 blur-[100px] opacity-60" />
      </div>

      <div className="max-w-7xl mx-auto relative z-10">
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ type: 'spring', bounce: 0.5 }}
          className="text-center max-w-3xl mx-auto mb-16"
        >
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-indigo-100 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 font-medium text-sm mb-6 shadow-sm">
            We&apos;re Here to Help
          </div>
          <h1 className="text-5xl md:text-7xl font-display font-bold text-slate-900 dark:text-white mb-6 tracking-tight uppercase">
            Get in <span className="text-transparent bg-clip-text bg-gradient-to-r from-indigo-600 to-blue-600">Touch</span>
          </h1>
          <p className="text-xl text-slate-600 dark:text-slate-300">Have questions about FaceSnap? Reach out to our team for support, sales, or general inquiries.</p>
        </motion.div>

        <div className="grid md:grid-cols-3 gap-8 lg:gap-12">
          <div className="md:col-span-1 space-y-8">
            <motion.div
              initial={{ opacity: 0, x: -30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ type: 'spring', bounce: 0.4, delay: 0.1 }}
              className="bg-white dark:bg-slate-900 p-10 rounded-[2.5rem] shadow-xl shadow-slate-200/50 border border-slate-100 dark:border-slate-800"
            >
              <h3 className="text-2xl font-bold text-slate-900 dark:text-white mb-8">Contact Information</h3>
              <div className="space-y-8">
                <div className="flex items-start gap-5 group">
                  <div className="w-12 h-12 rounded-2xl bg-indigo-50 dark:bg-indigo-950/50 flex items-center justify-center flex-shrink-0 group-hover:bg-indigo-600 group-hover:text-white text-indigo-600 dark:text-indigo-300 transition-colors duration-300 shadow-sm">
                    <Mail className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">Email Us</p>
                    <a href="mailto:support@facesnap.edu" className="text-slate-900 dark:text-white font-medium hover:text-indigo-600 transition-colors text-lg">support@facesnap.edu</a>
                  </div>
                </div>
                <div className="flex items-start gap-5 group">
                  <div className="w-12 h-12 rounded-2xl bg-indigo-50 dark:bg-indigo-950/50 flex items-center justify-center flex-shrink-0 group-hover:bg-indigo-600 group-hover:text-white text-indigo-600 dark:text-indigo-300 transition-colors duration-300 shadow-sm">
                    <Phone className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">Call Us</p>
                    <a href="tel:+18001234567" className="text-slate-900 dark:text-white font-medium hover:text-indigo-600 transition-colors text-lg">+1 (800) 123-4567</a>
                  </div>
                </div>
                <div className="flex items-start gap-5 group">
                  <div className="w-12 h-12 rounded-2xl bg-indigo-50 dark:bg-indigo-950/50 flex items-center justify-center flex-shrink-0 group-hover:bg-indigo-600 group-hover:text-white text-indigo-600 dark:text-indigo-300 transition-colors duration-300 shadow-sm">
                    <MapPin className="w-6 h-6" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider mb-1">Visit Us</p>
                    <p className="text-slate-900 dark:text-white font-medium text-lg leading-relaxed hover:text-indigo-600 transition-colors">
                      Mohagaon, Wardha Rd,<br />Nagpur, Maharashtra 441108
                    </p>
                  </div>
                </div>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: -30 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ type: 'spring', bounce: 0.4, delay: 0.2 }}
              className="bg-slate-900 p-10 rounded-[2.5rem] shadow-xl text-white relative overflow-hidden border-4 border-slate-100 dark:border-slate-800"
            >
              <div className="absolute -bottom-10 -right-10 w-32 h-32 bg-indigo-500 rounded-full blur-2xl opacity-30" />
              <h3 className="text-2xl font-bold mb-6 relative z-10">Support Hours</h3>
              <p className="text-slate-300 mb-2 font-medium relative z-10">Monday - Friday</p>
              <p className="font-bold text-2xl mb-8 relative z-10 text-indigo-400">9:00 AM - 6:00 PM EST</p>
              <p className="text-sm text-slate-400 relative z-10 leading-relaxed">We aim to respond to all inquiries within 24 business hours.</p>
            </motion.div>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', bounce: 0.4, delay: 0.3 }}
            className="md:col-span-2"
          >
            <div className="bg-white dark:bg-slate-900 p-10 md:p-14 rounded-[2.5rem] shadow-xl shadow-slate-200/50 border border-slate-100 dark:border-slate-800 h-full">
              {isSubmitted ? (
                <motion.div
                  initial={{ opacity: 0, scale: 0.9 }}
                  animate={{ opacity: 1, scale: 1 }}
                  transition={{ type: 'spring', bounce: 0.5 }}
                  className="h-full flex flex-col items-center justify-center text-center py-16"
                >
                  <div className="w-24 h-24 bg-emerald-100 dark:bg-emerald-950/50 text-emerald-600 rounded-full flex items-center justify-center mb-8 shadow-inner">
                    <CheckCircle2 className="w-12 h-12" />
                  </div>
                  <h3 className="text-4xl font-display font-bold text-slate-900 dark:text-white mb-4">Message Sent!</h3>
                  <p className="text-lg text-slate-600 dark:text-slate-300 mb-10 max-w-md">Thank you for reaching out. Our team will get back to you shortly.</p>
                  <button onClick={() => setIsSubmitted(false)} className="px-8 py-4 bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-200 font-bold rounded-full hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors shadow-sm hover:-translate-y-0.5">
                    Send Another Message
                  </button>
                </motion.div>
              ) : (
                <>
                  <h2 className="text-3xl font-bold text-slate-900 dark:text-white mb-10">Send us a Message</h2>
                  <form onSubmit={handleSubmit} className="space-y-8">
                    <div className="grid md:grid-cols-2 gap-8">
                      <div>
                        <label className="block text-sm font-bold text-slate-700 dark:text-slate-300 mb-3 uppercase tracking-wider ml-1">First Name</label>
                        <input type="text" required className="w-full px-5 py-4 rounded-2xl border border-slate-200 dark:border-slate-700 focus:ring-2 focus:ring-indigo-200 focus:border-indigo-500 outline-none transition-all bg-slate-50 dark:bg-slate-800 focus:bg-white dark:focus:bg-slate-800 text-slate-900 dark:text-slate-100 shadow-sm" placeholder="Jane" />
                      </div>
                      <div>
                        <label className="block text-sm font-bold text-slate-700 dark:text-slate-300 mb-3 uppercase tracking-wider ml-1">Last Name</label>
                        <input type="text" required className="w-full px-5 py-4 rounded-2xl border border-slate-200 dark:border-slate-700 focus:ring-2 focus:ring-indigo-200 focus:border-indigo-500 outline-none transition-all bg-slate-50 dark:bg-slate-800 focus:bg-white dark:focus:bg-slate-800 text-slate-900 dark:text-slate-100 shadow-sm" placeholder="Doe" />
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm font-bold text-slate-700 dark:text-slate-300 mb-3 uppercase tracking-wider ml-1">Email Address</label>
                      <input type="email" required className="w-full px-5 py-4 rounded-2xl border border-slate-200 dark:border-slate-700 focus:ring-2 focus:ring-indigo-200 focus:border-indigo-500 outline-none transition-all bg-slate-50 dark:bg-slate-800 focus:bg-white dark:focus:bg-slate-800 text-slate-900 dark:text-slate-100 shadow-sm" placeholder="jane@example.com" />
                    </div>
                    <div>
                      <label className="block text-sm font-bold text-slate-700 dark:text-slate-300 mb-3 uppercase tracking-wider ml-1">Subject</label>
                      <select className="w-full px-5 py-4 rounded-2xl border border-slate-200 dark:border-slate-700 focus:ring-2 focus:ring-indigo-200 focus:border-indigo-500 outline-none transition-all bg-slate-50 dark:bg-slate-800 focus:bg-white dark:focus:bg-slate-800 text-slate-900 dark:text-slate-100 appearance-none shadow-sm">
                        <option>General Inquiry</option>
                        <option>Technical Support</option>
                        <option>Sales & Pricing</option>
                        <option>Partnership</option>
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-bold text-slate-700 dark:text-slate-300 mb-3 uppercase tracking-wider ml-1">Message</label>
                      <textarea required rows={5} className="w-full px-5 py-4 rounded-2xl border border-slate-200 dark:border-slate-700 focus:ring-2 focus:ring-indigo-200 focus:border-indigo-500 outline-none transition-all bg-slate-50 dark:bg-slate-800 focus:bg-white dark:focus:bg-slate-800 resize-none text-slate-900 dark:text-slate-100 shadow-sm" placeholder="How can we help you?" />
                    </div>
                    <motion.button
                      whileHover={{ scale: 1.02 }}
                      whileTap={{ scale: 0.98 }}
                      type="submit"
                      className="w-full py-5 rounded-full bg-gradient-to-r from-indigo-600 to-blue-600 text-white font-bold text-lg hover:from-indigo-700 hover:to-blue-700 transition-all flex items-center justify-center gap-3 shadow-md shadow-indigo-500/20 hover:shadow-lg hover:shadow-indigo-500/30"
                    >
                      <Send className="w-6 h-6" />
                      Send Message
                    </motion.button>
                  </form>
                </>
              )}
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
