import React, { useState, useEffect, useCallback } from 'react';
import { useAuth, useToast } from '../contexts/AppContext';
import { Megaphone, Send, Users, CheckCircle, XCircle, Loader2, AlertCircle } from 'lucide-react';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../components/ui/select';

const Campaigns = () => {
  const { api } = useAuth();
  const { success, error } = useToast();
  
  const [templates, setTemplates] = useState([]);
  const [selectedTemplate, setSelectedTemplate] = useState('');
  const [phoneNumbers, setPhoneNumbers] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [isSending, setIsSending] = useState(false);
  const [campaignResult, setCampaignResult] = useState(null);

  const fetchTemplates = useCallback(async () => {
    try {
      const response = await api.get('/templates');
      // Filter only approved templates
      const approved = response.data.filter(
        (t) => t.status?.toLowerCase() === 'approved' || t.status?.toLowerCase() === 'active'
      );
      setTemplates(approved);
    } catch (err) {
      console.error('Failed to fetch templates:', err);
    } finally {
      setIsLoading(false);
    }
  }, [api]);

  useEffect(() => {
    fetchTemplates();
  }, [fetchTemplates]);

  const handleSendCampaign = async (e) => {
    e.preventDefault();
    
    if (!selectedTemplate) {
      error('Please select a template');
      return;
    }
    
    const numbers = phoneNumbers
      .split('\n')
      .map((n) => n.trim())
      .filter((n) => n.length > 0);
    
    if (numbers.length === 0) {
      error('Please enter at least one phone number');
      return;
    }

    setIsSending(true);
    setCampaignResult(null);

    try {
      const response = await api.post('/campaigns/send', {
        template_name: selectedTemplate,
        target_phone_numbers: numbers,
      });
      
      setCampaignResult(response.data);
      
      if (response.data.success) {
        success(`Campaign sent to ${response.data.sent_count} contacts`);
      } else {
        success(`Campaign sent: ${response.data.sent_count} succeeded, ${response.data.failed_count} failed`);
      }
    } catch (err) {
      error('Failed to send campaign');
      console.error('Campaign error:', err);
    } finally {
      setIsSending(false);
    }
  };

  const getPhoneCount = () => {
    return phoneNumbers
      .split('\n')
      .map((n) => n.trim())
      .filter((n) => n.length > 0).length;
  };

  return (
    <div className="p-6 md:p-8" data-testid="campaigns-page">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold tracking-tight mb-2" style={{ fontFamily: 'Cabinet Grotesk' }}>
          Campaigns
        </h1>
        <p className="text-zinc-400">
          Send bulk template messages to multiple contacts
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {/* Campaign Form */}
        <div className="bg-[#111] border border-white/5 rounded-xl p-6">
          <h2 className="text-xl font-bold mb-6" style={{ fontFamily: 'Cabinet Grotesk' }}>
            New Campaign
          </h2>

          <form onSubmit={handleSendCampaign} className="space-y-6">
            {/* Template Selection */}
            <div className="space-y-2">
              <label className="text-sm font-medium text-zinc-300">
                Select Template
              </label>
              {isLoading ? (
                <div className="h-11 bg-[#0A0A0A] border border-white/5 rounded-lg skeleton" />
              ) : templates.length === 0 ? (
                <div className="flex items-center gap-2 p-4 bg-amber-500/10 border border-amber-500/20 rounded-lg text-amber-400">
                  <AlertCircle className="w-5 h-5 flex-shrink-0" />
                  <p className="text-sm">No approved templates found. Create and get templates approved by Meta first.</p>
                </div>
              ) : (
                <Select value={selectedTemplate} onValueChange={setSelectedTemplate}>
                  <SelectTrigger 
                    className="w-full bg-[#0A0A0A] border-white/5"
                    data-testid="template-select"
                  >
                    <SelectValue placeholder="Choose a template..." />
                  </SelectTrigger>
                  <SelectContent className="bg-[#111] border-white/10">
                    {templates.map((template) => (
                      <SelectItem 
                        key={template.id} 
                        value={template.name}
                        className="focus:bg-white/5"
                      >
                        <div className="flex items-center gap-2">
                          <span>{template.name}</span>
                          <span className="text-xs text-zinc-500 uppercase">
                            ({template.language || 'EN'})
                          </span>
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            {/* Phone Numbers */}
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-zinc-300">
                  Phone Numbers
                </label>
                <span className="text-xs text-zinc-500">
                  <Users className="w-3 h-3 inline-block mr-1" />
                  {getPhoneCount()} contacts
                </span>
              </div>
              <textarea
                value={phoneNumbers}
                onChange={(e) => setPhoneNumbers(e.target.value)}
                placeholder="Enter phone numbers (one per line)&#10;e.g.&#10;+1234567890&#10;+0987654321"
                data-testid="phone-numbers-input"
                rows={8}
                className="w-full px-4 py-3 bg-[#0A0A0A] border border-white/5 rounded-lg font-mono text-sm focus:border-[#00E599] focus:ring-1 focus:ring-[#00E599] resize-none"
              />
              <p className="text-xs text-zinc-500">
                Include country code (e.g., +1 for US). One number per line.
              </p>
            </div>

            {/* Submit Button */}
            <button
              type="submit"
              disabled={isSending || templates.length === 0}
              data-testid="campaign-submit"
              className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-[#00E599] hover:bg-[#00CC88] text-black font-semibold rounded-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSending ? (
                <>
                  <Loader2 className="w-5 h-5 animate-spin" />
                  Sending Campaign...
                </>
              ) : (
                <>
                  <Send className="w-5 h-5" />
                  Send Campaign
                </>
              )}
            </button>
          </form>
        </div>

        {/* Campaign Results */}
        <div className="space-y-6">
          {/* Info Card */}
          <div className="bg-gradient-to-br from-[#00E599]/10 to-[#00D4FF]/10 border border-[#00E599]/20 rounded-xl p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-lg bg-[#00E599]/20 flex items-center justify-center">
                <Megaphone className="w-5 h-5 text-[#00E599]" />
              </div>
              <div>
                <h3 className="font-semibold">Campaign Tips</h3>
                <p className="text-sm text-zinc-400">Best practices for bulk messaging</p>
              </div>
            </div>
            <ul className="space-y-2 text-sm text-zinc-300">
              <li className="flex items-start gap-2">
                <CheckCircle className="w-4 h-4 text-[#00E599] flex-shrink-0 mt-0.5" />
                Only approved Meta templates can be used
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="w-4 h-4 text-[#00E599] flex-shrink-0 mt-0.5" />
                Messages are sent with 200ms delay for rate limits
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="w-4 h-4 text-[#00E599] flex-shrink-0 mt-0.5" />
                Include country code with phone numbers
              </li>
              <li className="flex items-start gap-2">
                <CheckCircle className="w-4 h-4 text-[#00E599] flex-shrink-0 mt-0.5" />
                Review Meta's messaging policies before sending
              </li>
            </ul>
          </div>

          {/* Results Card */}
          {campaignResult && (
            <div 
              className="bg-[#111] border border-white/5 rounded-xl p-6"
              data-testid="campaign-results"
            >
              <h3 className="text-lg font-semibold mb-4" style={{ fontFamily: 'Cabinet Grotesk' }}>
                Campaign Results
              </h3>
              
              <div className="grid grid-cols-2 gap-4 mb-6">
                <div className="bg-[#0A0A0A] rounded-lg p-4 text-center">
                  <div className="flex items-center justify-center gap-2 mb-2">
                    <CheckCircle className="w-5 h-5 text-[#00E599]" />
                    <span className="text-2xl font-bold text-[#00E599]">
                      {campaignResult.sent_count}
                    </span>
                  </div>
                  <p className="text-sm text-zinc-500">Sent</p>
                </div>
                <div className="bg-[#0A0A0A] rounded-lg p-4 text-center">
                  <div className="flex items-center justify-center gap-2 mb-2">
                    <XCircle className="w-5 h-5 text-red-400" />
                    <span className="text-2xl font-bold text-red-400">
                      {campaignResult.failed_count}
                    </span>
                  </div>
                  <p className="text-sm text-zinc-500">Failed</p>
                </div>
              </div>

              {/* Detailed Results */}
              {campaignResult.details && campaignResult.details.length > 0 && (
                <div className="max-h-60 overflow-y-auto">
                  <table className="w-full text-sm">
                    <thead className="sticky top-0 bg-[#111]">
                      <tr className="border-b border-white/5">
                        <th className="text-left py-2 text-zinc-400 font-medium">Phone</th>
                        <th className="text-right py-2 text-zinc-400 font-medium">Status</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-white/5">
                      {campaignResult.details.map((detail, idx) => (
                        <tr key={idx}>
                          <td className="py-2 font-mono text-zinc-300">{detail.phone}</td>
                          <td className="py-2 text-right">
                            {detail.status === 'sent' ? (
                              <span className="text-[#00E599]">Sent</span>
                            ) : (
                              <span className="text-red-400">Failed</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Campaigns;
